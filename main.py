import os
import logging
import unicodedata
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Configuração do logger
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuração do bot
BOT_TOKEN = "7633698590:AAGrm014F5D5FDPyP7f7-6QTkpE18CQ4WvY"
app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

# Caminho do arquivo Excel
EXCEL_FILE = 'DADOS_CLIENTES - INSTALAÇÃO E COORDENADAS.xlsx'

# Verificação e carregamento do arquivo Excel
try:
    import pandas as pd
    if not os.path.exists(EXCEL_FILE):
        raise FileNotFoundError(f"O arquivo '{EXCEL_FILE}' não foi encontrado.")
    df = pd.read_excel(EXCEL_FILE, engine="openpyxl")
    df.columns = [unicodedata.normalize('NFKD', str(col)).encode('ascii', 'ignore').decode('utf-8').strip() for col in df.columns]

    # Colunas esperadas
    expected_columns = ['Nome', 'Instalacao', 'Medidor', 'Latitude', 'Longitude']
    for col in expected_columns:
        if col not in df.columns:
            raise ValueError(f"A coluna esperada '{col}' não está presente no arquivo Excel.")
except ImportError:
    raise ImportError("O módulo 'pandas' com 'openpyxl' é necessário. Instale usando 'pip install pandas openpyxl'.")
except Exception as e:
    raise RuntimeError(f"Erro ao carregar o arquivo Excel: {e}")

# Função para normalizar texto
def normalize_text(text):
    nfkd_form = unicodedata.normalize('NFKD', text)
    return ''.join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

# Função de início
async def start(update: Update, context):
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
async def search(update: Update, context):
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

# Função para processar entrada do usuário
async def handle_message(update: Update, context):
    search_type = context.user_data.get('search_type')
    user_input = normalize_text(update.message.text)
    if not search_type:
        await update.message.reply_text("Por favor, escolha um tipo de pesquisa primeiro usando o comando /start.")
        return
    search_columns = {'nome': 'Nome', 'instalacao': 'Instalacao', 'medidor': 'Medidor'}
    search_col = search_columns[search_type]
    results = df[df[search_col].apply(lambda x: user_input in normalize_text(str(x)))]
    if results.empty:
        await update.message.reply_text("Nenhum resultado encontrado. Tente novamente.")
    else:
        response = "\n\n".join([
            f"Nome: {row['Nome']}\nInstalação: {row['Instalacao']}\nMedidor: {row['Medidor']}\n"
            f"Localização: [Abrir no Maps](https://www.google.com/maps?q={row['Latitude']},{row['Longitude']})"
            for _, row in results.iterrows()
        ])
        await update.message.reply_text(response, parse_mode="Markdown")

# Configuração do Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, application.bot)
    application.process_update(update)
    return 'OK', 200

# Adicionar Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(search, pattern='^(nome|instalacao|medidor)$'))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
