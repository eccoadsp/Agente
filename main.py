import os
import json
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
import winrm
from google.cloud import bigquery

app = Flask(__name__)
bq_client = bigquery.Client()

@app.route("/", methods=["GET"])
def index():
    return "OK"

@app.route("/", methods=["POST"])
def monitorar():
    dados = request.get_json()
    if not dados:
        return jsonify({"erro": "Requisição inválida. Dados ausentes."}), 400

    domain = dados.get("domain")
    username = dados.get("username")
    password = dados.get("password")
    servers = dados.get("servers")

    if not all([domain, username, password, servers]):
        return jsonify({"erro": "Parâmetros 'domain', 'username', 'password' e 'servers' são obrigatórios."}), 400

    resultados = []

    for host in servers:
        try:
            session = winrm.Session(
                target=host,
                auth=(f"{domain}\\{username}", password),
                transport="ntlm",
                server_cert_validation="ignore",
            )

            ps_script = r"""
            $cpu = (Get-Counter '\Processor(_Total)\% Processor Time').CounterSamples[0].CookedValue
            $mem = (Get-WmiObject Win32_OperatingSystem).FreePhysicalMemory
            $disk = Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='C:'"
            $totalDisk = [math]::Round($disk.Size / 1GB, 2)
            $freeDisk = [math]::Round($disk.FreeSpace / 1GB, 2)
            $freeDiskPercent = [math]::Round(($disk.FreeSpace / $disk.Size) * 100, 2)
            $cpu = [math]::Round($cpu, 2)
            $ram = [math]::Round($mem / 1024 / 1024, 2)
            [PSCustomObject]@{
                CPU = $cpu
                RAM_Livre_GB = $ram
                Disco_Total_GB = $totalDisk
                Disco_Livre_GB = $freeDisk
                Disco_Livre_Porcentagem = $freeDiskPercent
            } | ConvertTo-Json -Compress
            """

            result = session.run_ps(ps_script)

            if result.status_code != 0:
                raise Exception(f"Erro ao executar script: {result.std_err.decode()}")

            metrics = json.loads(result.std_out.decode())
            now_utc = datetime.now(timezone.utc)
            now_brt = now_utc.astimezone(timezone(timedelta(hours=-3)))

            registro = {
                "hostname": host,
                "cpu": metrics.get("CPU"),
                "ram": metrics.get("RAM_Livre_GB"),
                "disco_livre": metrics.get("Disco_Livre_GB"),
                "disco_total": metrics.get("Disco_Total_GB"),
                "disco_percentual_livre": metrics.get("Disco_Livre_Porcentagem"),
                "status": "OK",
                "timestamp_utc": now_utc,
                "timestamp_brasil": now_brt.strftime('%d/%m/%Y %H:%M:%S'),
            }

            try:
                table_id = "ecco-agent-dev.monitoramento.metricas_servidor"
                bq_client.insert_rows_json(table_id, [registro])
            except Exception as bq_err:
                registro["bigquery_error"] = str(bq_err)

            resultados.append({"hostname": host, "success": True, "metrics": registro})

        except Exception as erro:
            resultados.append({
                "hostname": host,
                "success": False,
                "error": str(erro)
            })

    return jsonify(resultados)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
