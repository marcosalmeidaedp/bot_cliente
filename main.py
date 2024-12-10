import os
import logging
import unicodedata
import pandas as pd
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Configuração do logger
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Inicialização do Flask
app = Flask(__name__)

# Carregar a base de dados
EXCEL_FILE = 'DADOS_CLIENTES - INSTALAÇÃO E COORDENADAS.xlsx'

if not os.path.exists(EXCEL_FILE):
    raise FileNotFoundError(f"Erro: O arquivo '{EXCEL_FILE}' não foi encontrado.")

try:
    df = pd.read_excel(EXCEL_FILE, engine="openpyxl")
    df.columns = [unicodedata.normalize('NFKD', str(col)).encode('ascii', 'ignore').decode('utf-8').strip() for col in df.columns]
    
    # Verificar colunas esperadas
    expected_columns = ['Nome', 'Instalacao', 'Medidor', 'Latitude', 'Longitude']
    for col in expected_columns:
        if col not in df.columns:
            raise ValueError(f"A coluna esperada '{col}' não está presente no arquivo Excel.")
except Exception as e:
    raise RuntimeError(f"Erro ao carregar o arquivo Excel: {e}")

# Função para normalizar texto
def normalize_text(text):
    nfkd_form = unicodedata.normalize('NFKD', text)
    return ''.join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

# Função para salvar logs de consulta
def log_consulta(usuario, telefone, consulta, resultado):
    with open("consultas_log.txt", "a", encoding="utf-8") as log_file:
        log_file.write(f"Usuário: {usuario}, Telefone: {telefone}, Consulta: {consulta}, Resultado: {resultado}\n")

# Função de início
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "Usuário"

    keyboard = [
        [InlineKeyboardButton("Pesquisar por Nome", callback_data='nome')],
        [InlineKeyboardButton("Pesquisar por Instalação", callback_data='instalacao')],
        [InlineKeyboardButton("Pesquisar por Medidor", callback_data='medidor')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_message = (
        f"Olá, {user_name}! 👋\n\n"
        f"Bem-vindo ao Bot de Pesquisa de Clientes. 🤖\n"
        f"Escolha abaixo o tipo de pesquisa que deseja realizar:"
    )

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

# Função para lidar com a pesquisa
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    search_type = query.data
    context.user_data['search_type'] = search_type

    prompt_messages = {
        'nome': "Digite o nome que deseja pesquisar:",
        'instalacao': "Digite o número da instalação que deseja pesquisar:",
        'medidor': "Digite o número do medidor que deseja pesquisar:",
    }

    await query.message.reply_text(prompt_messages[search_type])

# Processar entrada do usuário
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_type = context.user_data.get('search_type')
    user_input = normalize_text(update.message.text)

    if not search_type:
        await update.message.reply_text("Por favor, escolha um tipo de pesquisa primeiro usando o comando /start.")
        return

    search_columns = {
        'nome': 'Nome',
        'instalacao': 'Instalacao',
        'medidor': 'Medidor',
    }
    search_col = search_columns[search_type]

    def search_data(row):
        return all(part in normalize_text(str(row[search_col])) for part in user_input.split())

    results = df[df.apply(search_data, axis=1)]

    if results.empty:
        await update.message.reply_text("Nenhum resultado encontrado. Tente novamente.")
    else:
        response = ""
        for _, row in results.iterrows():
            response += "\n".join([f"{col}: {row[col]}" for col in df.columns])
            response += f"\nLocalização: [Abrir no Maps](https://www.google.com/maps?q={row['Latitude']},{row['Longitude']})\n\n"

        await update.message.reply_text(response, parse_mode="Markdown")

        # Log da consulta
        log_consulta(
            usuario=update.effective_user.first_name,
            telefone=update.effective_user.id,
            consulta=user_input,
            resultado="Resultado encontrado"
        )

        await update.message.reply_text("Sua consulta foi registrada na base de dados.")

        # Mostrar opções de encerrar ou reiniciar
        keyboard = [
            [InlineKeyboardButton("Nova consulta", callback_data='restart')],
            [InlineKeyboardButton("Encerrar", callback_data='close')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "O que você deseja fazer a seguir?", reply_markup=reply_markup
        )

# Fechar bot ou reiniciar interação
async def handle_restart_or_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'restart':
        await start(update, context)
    elif query.data == 'close':
        await query.message.reply_text("Obrigado por usar o bot! Até a próxima! 👋")
        return

# Configuração do Telegram Bot
BOT_TOKEN = os.environ.get('BOT_TOKEN')

application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(search, pattern='^(nome|instalacao|medidor)$'))
application.add_handler(CallbackQueryHandler(handle_restart_or_close, pattern='^(restart|close)$'))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook para Render
@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_json()
    update = Update.de_json(json_data, application.bot)
    application.process_update(update)
    return "ok", 200

# Inicialização do servidor Flask
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host="0.0.0.0", port=port)
