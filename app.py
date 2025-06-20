import os
import re
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

# --- CONFIGURAÇÃO INICIAL ---
load_dotenv()

# Inicializa o Flask
app = Flask(__name__)

# Configura as chaves de API a partir do .env
# É crucial que o arquivo .env esteja na mesma pasta que app.py
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Verifica se as chaves foram carregadas
if not YOUTUBE_API_KEY or not GEMINI_API_KEY:
    raise ValueError("Chaves de API não encontradas no arquivo .env. Verifique sua configuração.")

# Configura as APIs dos serviços
genai.configure(api_key=GEMINI_API_KEY)
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)


# --- FUNÇÕES AUXILIARES ---

def obter_id_de_url_canal(url):
    """
    Extrai o ID, nome de usuário ou handle de diferentes formatos de URL do YouTube.
    Retorna um dicionário com o tipo ('id', 'username', 'handle') e o valor.
    """
    # Padrão para /channel/UC...
    match = re.search(r'\/channel\/([a-zA-Z0-9_-]+)', url)
    if match:
        return {'type': 'id', 'value': match.group(1)}
    
    # Padrão para /user/username ou /c/username
    match = re.search(r'\/(user|c)\/([a-zA-Z0-9_-]+)', url)
    if match:
        return {'type': 'username', 'value': match.group(2)}

    # Padrão para /@handle
    match = re.search(r'\/@([a-zA-Z0-9_.-]+)', url)
    if match:
        return {'type': 'handle', 'value': match.group(1)}
        
    return None

def buscar_videos(query, time_type, time_value):
    """
    Busca vídeos no YouTube com base em uma query (ID do canal, palavra-chave)
    e um período de tempo (horas ou semanas).
    """
    params = {
        'part': 'snippet',
        'maxResults': 10,
        'order': 'date',
        'type': 'video'
    }

    # Calcula a data limite para a busca
    if time_type == 'weeks':
        delta = timedelta(weeks=int(time_value))
    else:
        delta = timedelta(hours=int(time_value))
    
    data_limite = (datetime.now(timezone.utc) - delta).isoformat().replace('+00:00', 'Z')
    params['publishedAfter'] = data_limite
    
    # Verifica se a query é uma URL de canal
    info_canal = obter_id_de_url_canal(query)
    
    if info_canal:
        channel_id = None
        if info_canal['type'] == 'id':
            channel_id = info_canal['value']
        elif info_canal['type'] in ['username', 'handle']:
            search_param = {'forUsername': info_canal['value']} if info_canal['type'] == 'username' else {'forHandle': info_canal['value']}
            try:
                channel_response = youtube.channels().list(part='id', **search_param).execute()
                if channel_response.get('items'):
                    channel_id = channel_response['items'][0]['id']
            except Exception as e:
                print(f"Erro ao buscar ID do canal para '{info_canal['value']}': {e}")
                channel_id = None
        
        if channel_id:
            params['channelId'] = channel_id
        else:
            params['q'] = query
    elif query:
        params['q'] = query

    search_response = youtube.search().list(**params).execute()
    return search_response.get('items', [])

def obter_transcricao(video_id):
    """Obtém a transcrição de um vídeo do YouTube."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'en'])
        return " ".join([item['text'] for item in transcript_list])
    except (NoTranscriptFound, TranscriptsDisabled, Exception):
        return None

def resumir_texto_com_gemini(texto_transcricao, titulo_video, tema_video="geral"):
    """Envia a transcrição para a API do Gemini para obter um resumo otimizado."""
    if not texto_transcricao:
        return "Não foi possível gerar um resumo, pois a transcrição não está disponível."

    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    # Nosso novo prompt dinâmico e estruturado
    prompt = f"""
[PERSONA]
Atue como um analista de conteúdo sênior e especialista em comunicação didática. Sua especialidade é destilar informações complexas de qualquer área ({tema_video}) e torná-las claras, concisas e acionáveis.

[TAREFA PRINCIPAL]
Analise a transcrição do vídeo a seguir, intitulado "{titulo_video}". Sua meta é criar um resumo denso e objetivo que capture a essência do conteúdo, os conceitos-chave e a lógica do raciocínio apresentado.

[REGRAS DE EXTRAÇÃO]
- Ignore introduções vagas, agradecimentos, pedidos de inscrição e despedidas.
- Elimine detalhes excessivamente técnicos, exemplos repetitivos e histórias pessoais que não agregam ao conceito principal.
- Preserve o "porquê" e o "como" das informações, não apenas o "o quê".

[FORMATO DE SAÍDA]
Apresente o resumo usando a estrutura mais adequada para o conteúdo do vídeo. Escolha uma das seguintes opções:
1.  **Para tutoriais ou guias ("Como fazer"):** Use um formato de **Checklist Acionável**, com os passos claros e diretos.
2.  **Para vídeos conceituais ou explicativos:** Use **Tópicos e Subtópicos Hierarquizados** (bullet points com indentação) para mostrar a estrutura lógica e a relação entre as ideias.
3.  **Para notícias, debates ou análises:** Use um **Sumário Executivo** com os 3 a 5 pontos mais críticos e suas implicações.

[TOM E ESTILO]
- **Tom:** Objetivo, direto e informativo.
- **Linguagem:** Simples e acessível, evitando jargões desnecessários.
- **Foco:** Clareza e utilidade prática para quem não tem tempo de assistir ao vídeo completo.
- **Use a sintaxe Markdown (ex: `**negrito**` para ênfase, `*` ou `-` para listas) para estruturar sua resposta e melhorar a legibilidade.**

[CONTEÚDO DO VÍDEO PARA ANÁLISE]
---
{texto_transcricao}
---
"""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Ocorreu um erro ao gerar o resumo com a API: {str(e)}"

# --- ROTAS DA API ---

@app.route('/')
def index():
    """Renderiza a página HTML principal."""
    return render_template('index.html')

@app.route('/api/summarize', methods=['POST'])
def summarize_videos():
    """
    Endpoint da API que recebe os parâmetros do frontend,
    processa os vídeos e retorna os resumos em formato JSON.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Requisição inválida"}), 400

    time_type = data.get('timeType')
    time_value = data.get('timeValue')
    channel_query = data.get('channel', '')

    videos = buscar_videos(channel_query, time_type, time_value)
    
    summaries = []
    for video in videos:
        video_id = video['id']['videoId']
        video_title = video['snippet']['title']
        channel_title = video['snippet']['channelTitle']
        
        transcricao = obter_transcricao(video_id)
        if transcricao:
            resumo = resumir_texto_com_gemini(transcricao, video_title, tema_video=channel_title)
            summaries.append({
                "title": video_title,
                "channel": channel_title,
                "summary": resumo
            })

    return jsonify(summaries)

# --- EXECUÇÃO DO SERVIDOR ---
if __name__ == '__main__':
    # Executa o servidor Flask em modo de desenvolvimento
    app.run(debug=True, port=5000)