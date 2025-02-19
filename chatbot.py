import os
import json
import logging
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext

# 🔹 Carregar variáveis do .env
load_dotenv()

# Configuração do logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 🔹 Configuração das APIs usando variáveis do .env
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SAMPLE_SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")  # ID da planilha
SAMPLE_RANGE_NAME = "Página1!A1:B28"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Chave da API Gemini
genai.configure(api_key=GEMINI_API_KEY)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Token do Bot Telegram

# Banco de respostas pré-definidas
predefined_answers = {
    "Quantas e quais são as esteiras do contrato 71?": "São 27 esteiras no contrato 71. Aqui está a lista:\n"
                                                       "1. ESTEIRA - TFNAP - IX - 170256\n"
                                                       "2. ESTEIRA - TFNAP-IX-170250\n"
                                                       "... (continue a lista)",
    "Quantos esteiras estão funcionando?": "No contrato 71, há **10 esteiras funcionando**.",
    "Quantos equipamentos estão inoperantes no contrato 71?": "No contrato 71, há **4 esteiras inoperantes**.",
    "Quantos equipamentos estão no contrato 02?": "O contrato 02 possui **14 equipamentos** cadastrados.",
    "Quantos equipamentos estão funcionando no contrato 02?": "No contrato 02, há **12 equipamentos funcionando**.",
    "Quantos equipamentos estão inoperantes no contrato 02?": "No contrato 02, há **1 equipamento inoperante**.",
    "Quais equipamentos possuem pendências?": "Apenas **1 equipamento no contrato 02** possui pendências:\n"
                                              "- BODYSCAN - 1299000006 - FUNCIONANDO COM PENDÊNCIA."
}

def get_sheet_data():
    """Obtém os dados da planilha do Google Sheets"""
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
        result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=SAMPLE_RANGE_NAME).execute()
        values = result.get("values", [])
        return values
    except HttpError as err:
        logger.error(f"Erro ao acessar a planilha: {err}")
        return None

def ask_gemini(question, data):
    """Faz uma pergunta personalizada ao Gemini sobre os dados da planilha"""
    if question in predefined_answers:
        return predefined_answers[question]

    if not data:
        return "Não há dados disponíveis na planilha."

    formatted_data = "\n".join([", ".join(row) for row in data])
    prompt = f"""
    Os seguintes são dados extraídos de uma planilha do Google Sheets:

    {formatted_data}

    Com base nesses dados, responda à seguinte pergunta de forma clara e precisa:
    {question}
    """

    try:
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Erro ao chamar a API do Gemini: {e}")
        return "Erro ao consultar a IA. Tente novamente mais tarde."

# Função para responder mensagens no Telegram
async def handle_message(update: Update, context: CallbackContext):
    try:
        user_question = update.message.text
        sheet_data = get_sheet_data()

        if user_question.lower() == "sair":
            await update.message.reply_text("Até mais! 🚀")
            return

        response = ask_gemini(user_question, sheet_data)
        await update.message.reply_text(f"**Pergunta:** {user_question}\n**Resposta:** {response}")

    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}")
        await update.message.reply_text("Erro ao processar sua mensagem. Tente novamente mais tarde.")

# Função para responder ao comando /start no Telegram
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Olá! Sou um bot de análise de dados do Google Sheets! Envie uma pergunta.")

# Handler de erros globais
async def error_handler(update: object, context: CallbackContext) -> None:
    logger.error(f"Erro encontrado: {context.error}")
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("❌ Ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde!")

# Configurar o bot do Telegram
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Adicionando handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)  # Captura erros globais

    # Iniciar o bot
    app.run_polling()

if __name__ == "__main__":
    main()
