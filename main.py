import os
import winrm
import pytz
from flask import Flask, request, jsonify
from datetime import datetime
from google.cloud import firestore

app = Flask(__name__)
db = firestore.Client()

def coletar_metricas(hostname, domain, username, password):
    try:
        full_username = f"{domain}\\{username}"
        session = winrm.Session(target=hostname,
                                auth=(full_username, password),
                                transport='ntlm',
                                server_cert_validation='ignore')

        ps_script = """
        $cpu = (Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue
        $mem = Get-WmiObject Win32_OperatingSystem
        $totalMem = $mem.TotalVisibleMemorySize
        $freeMem = $mem.FreePhysicalMemory
        $usedMemMB = [math]::Round(($totalMem - $freeMem) / 1024, 2)

        $disks = Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
            [PSCustomObject]@{
                DeviceID = $_.DeviceID
                SizeGB = [math]::Round($_.Size / 1GB, 2)
                FreeGB = [math]::Round($_.FreeSpace / 1GB, 2)
            }
        }

        $result = [PSCustomObject]@{
            CPU = [math]::Round($cpu, 2)
            RAM_MB = $usedMemMB
            Disks = $disks
        }

        $result | ConvertTo-Json -Depth 3
        """
        response = session.run_ps(ps_script)

        if response.status_code != 0:
            raise Exception(response.std_err.decode("utf-8"))

        output = response.std_out.decode("utf-8")
        return jsonify({"success": True, "hostname": hostname, "metrics": output})

    except Exception as e:
        return jsonify({"success": False, "hostname": hostname, "error": str(e)})

def gravar_firestore(registro):
    timestamp_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
    br_tz = pytz.timezone("America/Sao_Paulo")
    timestamp_brasil = timestamp_utc.astimezone(br_tz)

    registro['timestamp_utc'] = timestamp_utc.isoformat()
    registro['timestamp_brasil'] = timestamp_brasil.strftime("%d-%m-%Y %H:%M:%S")

    db.collection("servidores-monitorados").add(registro)

@app.route("/", methods=["POST"])
def monitorar():
    data = request.json
    domain = data.get("domain")
    username = data.get("username")
    password = data.get("password")
    servers = data.get("servers")

    if not all([domain, username, password, servers]):
        return jsonify({"success": False, "error": "Parâmetros ausentes"}), 400

    resultados = []
    for host in servers:
        try:
            result = coletar_metricas(host, domain, username, password)
            json_result = result.get_json()

            if json_result.get("success"):
                gravar_firestore({
                    "hostname": json_result.get("hostname"),
                    "dados": json_result.get("metrics")
                })

            resultados.append(json_result)
        except Exception as e:
            resultados.append({"hostname": host, "success": False, "error": str(e)})

    return jsonify(resultados)

@app.route('/', methods=['GET'])
def health():
    return 'OK', 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
