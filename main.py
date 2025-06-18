import os
from flask import Flask, request, jsonify
import winrm
import getpass

app = Flask(__name__)

@app.route("/", methods=["POST"])
def get_metrics():
    try:
        # Parâmetros esperados via JSON
        data = request.get_json()
        domain = data.get("domain")
        hostname = data.get("hostname")
        username = data.get("username")
        password = data.get("password")

        if not all([domain, hostname, username, password]):
            return jsonify({"error": "Parâmetros ausentes"}), 400

        full_user = f"{domain}\\{username}"

        session = winrm.Session(
            f"https://{hostname}:5986/wsman",
            auth=(full_user, password),
            transport='ntlm',
            server_cert_validation='ignore'
        )

        # PowerShell Script para coletar métricas
        ps_script = """
        $cpu = (Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue
        $ram = (Get-WmiObject Win32_OperatingSystem).FreePhysicalMemory
        $disk = (Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace
        $totalDisk = (Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='C:'").Size

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
            return jsonify({"error": "Falha ao executar script remoto", "details": result.std_err.decode()}), 500

        return jsonify({"metrics": result.std_out.decode().strip()})

    except Exception as e:
        return jsonify({"error": "Erro inesperado", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
