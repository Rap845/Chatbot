import os
import json
import re
import asyncio
import google.generativeai as genai  # API do Gemini
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv  # Carregar variáveis de ambiente

# 🔹 Carregar variáveis do arquivo .env
load_dotenv()

# 🔹 Configuração das chaves de API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# 🔹 Configurar a API do Gemini com a chave carregada
genai.configure(api_key=GOOGLE_API_KEY)

# 🔹 Definição do escopo para acessar a API do Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 🔹 Criando o menu de botões para o Telegram (inicialmente vazio)
MENU_KEYBOARD = ReplyKeyboardMarkup(
    [["📅 Vigência do contrato 71", "🗑 Limpar histórico"]],
    resize_keyboard=True, one_time_keyboard=False
)

# 🔹 Lista de usuários autorizados (ignora maiúsculas e minúsculas)
AUTHORIZED_USERS = {"raphael", "mariana", "nilza", "matheus"}

# 🔹 Dicionário para armazenar o estado dos usuários
USER_STATE = {}

def generate_gemini_response(prompt):
    """Gera uma resposta personalizada usando o Gemini AI"""
    model = genai.GenerativeModel("gemini-1.5-pro-latest")  # Modelo Gemini Pro
    response = model.generate_content(prompt)
    return response.text.strip()

def sanitize_response(response):
    """Remove caracteres especiais indesejados da resposta"""
    response = re.sub(r"\*", "", response)  # Remove todos os asteriscos
    response = re.sub(r"[^\w\s,.!?%€$£-]", "", response)  # Mantém caracteres essenciais
    return response.strip()

def get_google_sheets_data():
    """Autentica e busca dados da planilha no Google Sheets"""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        # Adicionar o range correto
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="Página1!A1:D28").execute()
        values = result.get("values", [])

        if not values:
            return "Nenhum dado encontrado."

        return values

    except HttpError as err:
        return str(err)

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Responde às perguntas do usuário no Telegram"""
    chat_id = update.message.chat_id
    user_text = update.message.text.strip().lower()

    # Verifica se o usuário já foi autorizado
    if chat_id not in USER_STATE:
        # Se o usuário não forneceu um nome ainda, verifica o nome digitado
        if user_text in AUTHORIZED_USERS:
            USER_STATE[chat_id] = "authorized"
            await update.message.reply_text("✅ Acesso autorizado! Como posso te ajudar?", reply_markup=MENU_KEYBOARD)
        else:
            await update.message.reply_text("❌ Usuário não autorizado. Você não pode interagir com o bot.")
        return

    # Se o usuário clicar no botão "📅 Vigência do contrato 71"
    if user_text == "📅 vigência do contrato 71":
        await update.message.reply_text("📌 O contrato 71 tem vigência até 29/04/2025.")
        return

    # Se o usuário clicar no botão "🗑 Limpar histórico"
    if user_text == "🗑 limpar histórico":
        await clear_chat_history(update, context)
        return

    data = get_google_sheets_data()

    if isinstance(data, str):
        await update.message.reply_text(f"⚠️ Erro ao acessar a planilha: {data}")
        return

    # Converter os dados da planilha para JSON legível
    json_data = json.dumps(data, indent=2)

    # Criar um prompt detalhado para o Gemini AI
    prompt = f"""
    Você é um assistente especializado em análise de dados de planilhas. 
    Aqui estão os dados da planilha em formato JSON:
    {json_data}

    Responda à seguinte pergunta do usuário com base nesses dados:
    {user_text}
    """

    response = generate_gemini_response(prompt)

    # Remover caracteres especiais antes de enviar
    clean_response = sanitize_response(response)

    await update.message.reply_text(clean_response)

async def clear_chat_history(update: Update, context: CallbackContext) -> None:
    """Limpa o histórico de mensagens do chat"""
    chat_id = update.message.chat_id

    try:
        await context.bot.send_message(chat_id, "🗑 Limpando histórico de conversa...")
        async for message in context.bot.get_chat_history(chat_id):
            await context.bot.delete_message(chat_id, message.message_id)

        await context.bot.send_message(chat_id, "✅ Histórico limpo com sucesso!", reply_markup=MENU_KEYBOARD)
    except Exception as e:
        await context.bot.send_message(chat_id, f"⚠️ Erro ao limpar histórico: {e}")

async def start(update: Update, context: CallbackContext) -> None:
    """Mensagem de boas-vindas e solicitação do nome do usuário"""
    chat_id = update.message.chat_id

    # Resetar o estado do usuário ao iniciar o bot
    USER_STATE.pop(chat_id, None)

    await update.message.reply_text(
        "👋 Olá! Sou um bot que analisa dados dos contratos. "
        "Antes de continuar, por favor, me diga seu nome:"
    )

def main():
    """Inicia o bot do Telegram"""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Comando /start
    app.add_handler(CommandHandler("start", start))

    # Mensagens normais e cliques nos botões
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Inicia o bot
    print("🤖 Bot está rodando no Telegram...")
    app.run_polling()

if __name__ == "__main__":
    main()