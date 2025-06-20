# Use imagem oficial Python
FROM python:3.11-slim

# Define diretório de trabalho
WORKDIR /app

# Copia o requirements.txt e instala as dependências
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Expõe a porta esperada pelo Cloud Run
ENV PORT 8080
EXPOSE 8080

# Usa gunicorn para rodar a app Flask
CMD exec gunicorn --bind :$PORT main:app

