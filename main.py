import os
from flask import Flask, request, jsonify
import winrm

app = Flask(__name__)

@app.route("/", methods=["POST"])
def get_metrics():
    try:
        data = request.get_json()
        servers = data.get("servers")

        if not servers or not isinstance(servers, list):
            return jsonify({"error": "Parâmetro 'servers' ausente ou inválido."}), 400

        results = []

        for server in servers:
            domain = server.get("domain")
            hostname = server.get("hostname")
            username = server.get("username")
            password = server.get("password")

            if not all([domain, hostname, username, password]):
                results.append({"hostname": hostname or "undefined", "error": "Parâmetros ausentes."})
                continue

            full_user = f"{domain}\\{username}"

            try:
                session = winrm.Session(
                    f"https://{hostname}:5986/wsman",
                    auth=(full_user, password),
                    transport='ntlm',
                    server_cert_validation='ignore'
                )

                ps_script = """
                $cpu = (Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue
                $ram = (Get-WmiObject Win32_OperatingSystem).FreePhysicalMemory
                $disk = (Get-WmiObject Win32_LogicalDisk -Filter \"DeviceID='C:'\").FreeSpace
                $totalDisk = (Get-WmiObject Win32_LogicalDisk -Filter \"DeviceID='C:'\").Size

                $result = @{
                    CPU = [math]::Round($cpu,2)
                    RAM_Free_MB = [math]::Round($ram / 1024,2)
                    Disk_Free_GB = [math]::Round($disk / 1GB,2)
                    Disk_Total_GB = [math]::Round($totalDisk / 1GB,2)
                }
                $result | ConvertTo-Json
                """

                result = session.run_ps(ps_script)

                if result.status_code != 0:
                    results.append({
                        "hostname": hostname,
                        "error": "Erro na execução do script",
                        "details": result.std_err.decode()
                    })
                else:
                    results.append({
                        "hostname": hostname,
                        "metrics": result.std_out.decode().strip()
                    })

            except Exception as e:
                results.append({"hostname": hostname, "error": str(e)})

        return jsonify({"results": results})

    except Exception as e:
        return jsonify({"error": "Erro inesperado", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
