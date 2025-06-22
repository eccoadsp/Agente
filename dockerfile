FROM python:3.11-slim

# Diretório de trabalho no container
WORKDIR /app

# Copia dependências e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Comando de inicialização do container (Gunicorn ouvindo na porta 8080)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
