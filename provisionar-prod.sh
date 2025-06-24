#!/bin/bash
# Script de provisionamento completo do ambiente Produção

# Defina aqui sua conta de faturamento (substitua pelo seu billing ID real)
BILLING_ACCOUNT="INSIRA_SEU_BILLING_ID"

# 1. Criar projeto (com billing)
echo "[1/10] Criando projeto GCP com billing..." && gcloud projects create ecco-agent-gcp --name="Ecco Agent Produção" && gcloud beta billing projects link ecco-agent-gcp --billing-account=$BILLING_ACCOUNT && gcloud config set project ecco-agent-gcp && 
echo "[2/10] Reservando IP estático..." && gcloud compute addresses create cloud-run-static-ip-prod --region=southamerica-east1 && 
echo "[3/10] Criando sub-rede..." && gcloud compute networks subnets create cloud-run-subnet-prod --network=default --range=10.22.0.0/28 --region=southamerica-east1 && 
echo "[4/10] Criando Cloud Router..." && gcloud compute routers create cloud-run-router-prod --region=southamerica-east1 --network=default && 
echo "[5/10] Criando Cloud NAT..." && gcloud compute routers nats create nat-prod --router=cloud-run-router-prod --region=southamerica-east1 --nat-external-ip-pool=cloud-run-static-ip-prod --nat-all-subnet-ip-ranges && 
echo "[6/10] Criando VPC Access Connector..." && gcloud compute networks vpc-access connectors create cr-connector-prod --region=southamerica-east1 --subnet=cloud-run-subnet-prod && 
echo "[7/10] Criando conta de serviço..." && gcloud iam service-accounts create agent-prod --display-name="Agent Prod Runner" && 
echo "[8/10] Concedendo permissões..." && gcloud projects add-iam-policy-binding ecco-agent-gcp --member="serviceAccount:agent-prod@ecco-agent-gcp.iam.gserviceaccount.com" --role="roles/editor" && 
echo "[9/10] Fazendo deploy do container..." && gcloud run deploy winrm-metrics --source . --region=southamerica-east1 --platform=managed --allow-unauthenticated --service-account=agent-prod@ecco-agent-gcp.iam.gserviceaccount.com && 
echo "[10/10] Atualizando configuração de rede do Cloud Run..." && gcloud run services update winrm-metrics --region=southamerica-east1 --vpc-connector=cr-connector-prod --vpc-egress=all-traffic && 
echo "
✅ Ambiente de Produção provisionado com sucesso."
