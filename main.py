import winrm
import json
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/', methods=['GET'])
def coletar_metricas():

    try:
        host = os.environ['WINRM_HOST']
        dominio = os.environ['WINRM_DOMINIO']
        usuario = os.environ['WINRM_USUARIO']
        senha = os.environ['WINRM_SENHA']
        username = f"{dominio}\\{usuario}"

        session = winrm.Session(
            f'https://{host}:5986',
            auth=(username, senha),
            transport='ntlm',
            server_cert_validation='ignore'
        )

        ps_script = """
        $cpu = Get-Counter '\\Processor(_Total)\\% Processor Time' | Select -ExpandProperty CounterSamples | Select -ExpandProperty CookedValue;
        $ram = Get-WmiObject Win32_OperatingSystem | Select -ExpandProperty FreePhysicalMemory;
        $disk = Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3" | Select DeviceID,FreeSpace,Size;
        $result = [PSCustomObject]@{
          cpu_percent = [math]::Round($cpu, 2);
          free_ram_mb = [math]::Round($ram / 1024, 2);
          disks = $disk | ForEach-Object {
            @{
              drive = $_.DeviceID;
              free_gb = [math]::Round($_.FreeSpace / 1GB, 2);
              size_gb = [math]::Round($_.Size / 1GB, 2);
            }
          }
        };
        $result | ConvertTo-Json -Depth 3
        """

        result = session.run_ps(ps_script)

        if result.status_code == 0:
            output = result.std_out.decode('utf-8')
            metrics = json.loads(output)
            return jsonify(metrics), 200
        else:
            return jsonify({"erro": result.std_err.decode('utf-8')}), 500

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
