import os
import winrm
import pytz
import logging
from flask import Flask, request, jsonify
from datetime import datetime

try:
    from google.cloud import firestore
    firestore_available = True
except Exception as e:
    firestore_available = False
    logging.error(f"Firestore import failed: {e}")

app = Flask(__name__)
db = None

@app.route('/', methods=['POST'])
def monitorar():
    global db

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
            full_username = f"{domain}\\{username}"
            session = winrm.Session(
                target=host,
                auth=(full_username, password),
                transport='ntlm',
                server_cert_validation='ignore'
            endpoint=f"https://{host}:5986/wsman"   
            )

            ps_script = """
            $cpu = (Get-Counter '\Processor(_Total)\% Processor Time').CounterSamples.CookedValue
            $mem = Get-WmiObject Win32_OperatingSystem
            $freeMemMB = [math]::Round($mem.FreePhysicalMemory / 1024, 2)

            $disco = Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='C:'"
            $totalGB = [math]::Round($disco.Size / 1GB, 2)
            $livreGB = [math]::Round($disco.FreeSpace / 1GB, 2)
            $percentLivre = [math]::Round(($livreGB / $totalGB) * 100, 2)

            $obj = [PSCustomObject]@{
                CPU = [math]::Round($cpu, 2)
                RAM_Livre_GB = $freeMemMB / 1024
                Disco_Total_GB = $totalGB
                Disco_Livre_GB = $livreGB
                Disco_Livre_Porcentagem = $percentLivre
            }
            $obj | ConvertTo-Json -Depth 2
            """

            result = session.run_ps(ps_script)
            output = result.std_out.decode("utf-8")
            metrics = eval(output) if output else {}
            now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
            now_brt = now_utc.astimezone(pytz.timezone('America/Sao_Paulo'))

            registro = {
                "servidor": host,
                "dominio": domain,
                "usuario": username,
                "coletado_em_utc": now_utc.isoformat(),
                "coletado_em_brt": now_brt.strftime('%d/%m/%Y %H:%M:%S'),
                "cpu": metrics.get("CPU"),
                "ram_gb_livre": metrics.get("RAM_Livre_GB"),
                "disco_total_gb": metrics.get("Disco_Total_GB"),
                "disco_gb_livre": metrics.get("Disco_Livre_GB"),
                "disco_percent_livre": metrics.get("Disco_Livre_Porcentagem")
            }

            if firestore_available:
                try:
                    if db is None:
                        db = firestore.Client()
                    db.collection("metricas").add(registro)
                except Exception as db_err:
                    registro["firestore_error"] = str(db_err)

            resultados.append({"success": True, "hostname": host, "metrics": registro})

        except Exception as e:
            resultados.append({"success": False, "hostname": host, "error": str(e)})

    return jsonify(resultados)

@app.route('/', methods=['GET'])
def health():
    return 'OK', 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))