import os
import winrm
import pytz
import logging
from flask import Flask, request, jsonify
from datetime import datetime
from google.cloud import firestore

app = Flask(__name__)
db = firestore.Client()

@app.route('/', methods=['POST'])
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
            full_username = f"{domain}\\{username}"
            target = f"https://{host}:5986/wsman"

            session = winrm.Session(
                target=target,
                auth=(full_username, password),
                transport='ntlm',
                server_cert_validation='ignore'
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

            try:
                db.collection("metricas").add(registro)
            except Exception as db_err:
                registro["firestore_error"] = str(db_err)

            resultados.append({"success": True, "hostname": host, "metrics": registro})

        except Exception as e:
            import traceback
            erro_completo = traceback.format_exc()
            resultados.append({
                "success": False,
                "hostname": host,
                "error": str(e),
                "trace": erro_completo
            })

    return jsonify(resultados)

@app.route('/', methods=['GET'])
def health():
    return 'OK', 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))