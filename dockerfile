# Imagem base
FROM python:3.11-slim

# Diretório de trabalho
WORKDIR /app

# Copia os arquivos
COPY . .

# Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta que o Cloud Run espera
EXPOSE 8080

# Variável de ambiente padrão usada pelo Cloud Run
ENV PORT=8080

# Comando de inicialização
CMD ["python", "main.py"]
