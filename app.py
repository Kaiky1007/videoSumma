import os
import re
import json
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from celery import Celery, Task

load_dotenv()
app = Flask(__name__)
app.config.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0'
)

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['result_backend'],
        broker=app.config['broker_url']      
    )
    celery.conf.update(app.config)

    class ContextTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

celery = make_celery(app)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not YOUTUBE_API_KEY or not GEMINI_API_KEY:
    raise ValueError("Chaves de API não encontradas no arquivo .env. Verifique sua configuração.")

genai.configure(api_key=GEMINI_API_KEY)
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

def obter_id_de_url_canal(url):
    if not url: return None
    match = re.search(r'\/channel\/([a-zA-Z0-9_-]+)', url)
    if match: return {'type': 'id', 'value': match.group(1)}
    match = re.search(r'\/(user|c)\/([a-zA-Z0-9_-]+)', url)
    if match: return {'type': 'username', 'value': match.group(2)}
    match = re.search(r'\/@([a-zA-Z0-9_.-]+)', url)
    if match: return {'type': 'handle', 'value': match.group(1)}
    return None

def buscar_videos(query_string, time_type, time_value):
    all_videos = {}
    queries = [q.strip() for q in query_string.split(',') if q.strip()]

    if not queries:
        queries.append(None)

    for query in queries:
        params = {
            'part': 'snippet',
            'maxResults': 10,
            'order': 'date',
            'type': 'video'
        }
        try:
            time_val_int = int(time_value)
            if time_type == 'weeks':
                delta = timedelta(weeks=time_val_int)
            else:
                delta = timedelta(hours=time_val_int)
            params['publishedAfter'] = (datetime.now(timezone.utc) - delta).isoformat().replace('+00:00', 'Z')
        except (ValueError, TypeError):
            return []

        info_canal = obter_id_de_url_canal(query)
        if info_canal:
            channel_id = None
            if info_canal['type'] == 'id': channel_id = info_canal['value']
            elif info_canal['type'] in ['username', 'handle']:
                search_param = {'forUsername': info_canal['value']} if info_canal['type'] == 'username' else {'forHandle': info_canal['value']}
                try:
                    channel_response = youtube.channels().list(part='id', **search_param).execute()
                    if channel_response.get('items'): channel_id = channel_response['items'][0]['id']
                except Exception as e: print(f"Erro ao buscar ID do canal: {e}")
            if channel_id: params['channelId'] = channel_id
            else: params['q'] = query
        elif query:
            params['q'] = query
        
        try:
            search_response = youtube.search().list(**params).execute()
            for item in search_response.get('items', []):
                all_videos[item['id']['videoId']] = item
        except Exception as e:
            print(f"ERRO CRÍTICO na busca da API do YouTube para a query '{query}': {e}")
            
    return list(all_videos.values())

def obter_transcricao(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'en'])
        return " ".join([item['text'] for item in transcript_list])
    except Exception: return None

def resumir_texto_com_gemini(texto_transcricao, titulo_video, tema_video="geral"):
    if not texto_transcricao: return "Transcrição indisponível."
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
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
1.  Para tutoriais ou guias ("Como fazer"): Use um formato de Checklist Acionável, com os passos claros e diretos.
2.  Para vídeos conceituais ou explicativos: Use Tópicos e Subtópicos Hierarquizados (bullet points com indentação) para mostrar a estrutura lógica e a relação entre as ideias.
3.  Para notícias, debates ou análises: Use um Sumário Executivo com os 3 a 5 pontos mais críticos e suas implicações.

[TOM E ESTILO]
- Tom: Objetivo, direto e informativo.
- Linguagem: Simples e acessível, evitando jargões desnecessários.
- Foco: Clareza e utilidade prática para quem não tem tempo de assistir ao vídeo completo.
- Use a sintaxe Markdown (ex: `**negrito**` para ênfase, `*` ou `-` para listas) para estruturar sua resposta e melhorar a legibilidade.

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

def gerar_analise_consolidada_com_gemini(resumos_compilados):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
    Com base no conjunto de resumos de vídeos de finanças a seguir, sua tarefa é criar uma análise consolidada.

    [TAREFA]
    1.  Identifique os 3 a 5 temas principais que foram discutidos no geral.
    2.  Para cada tema, mencione brevemente quais canais o abordaram.
    3.  Conclua com uma observação sobre o sentimento geral (otimista, cauteloso, misto) que os vídeos transmitem.

    [FORMATO]
    Use tópicos e subtópicos em Markdown para uma apresentação clara e organizada.

    [RESUMOS PARA ANÁLISE]
    ---
    {resumos_compilados}
    ---
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Ocorreu um erro ao gerar a análise consolidada: {str(e)}"
    
@celery.task(bind=True, name='tasks.generate_summaries')
def generate_summaries_task(self, channel_query, time_type, time_value):
    """
    Esta é a tarefa que roda em segundo plano para não travar a aplicação.
    O 'bind=True' nos dá acesso ao 'self', que representa a própria tarefa.
    """
    try:
        # 1. Cria um diretório único para este lote de resumos
        batch_id = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        batch_dir = os.path.join(DATA_DIR, batch_id)
        os.makedirs(batch_dir)

        # 2. Busca os vídeos na API do YouTube
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': '?', 'status': 'Buscando vídeos...'})
        videos = buscar_videos(channel_query, time_type, time_value)

        if not videos:
            return {'status': 'Concluído', 'batch_id': batch_id, 'summary_count': 0, 'message': 'Nenhum vídeo novo encontrado no período selecionado.'}

        # 3. Processa cada vídeo encontrado
        summary_metadata = []
        total_videos = len(videos)
        for i, video in enumerate(videos):
            # Atualiza o estado para o frontend saber o progresso
            self.update_state(
                state='PROGRESS',
                meta={'current': i, 'total': total_videos, 'status': f'Processando vídeo {i+1} de {total_videos}: {video["snippet"]["title"]}'}
            )

            video_id = video['id']['videoId']
            video_title = video['snippet']['title']
            channel_title = video['snippet']['channelTitle']
            
            transcription = obter_transcricao(video_id)
            summary_text = resumir_texto_com_gemini(transcription, video_title, channel_title)
            
            # Define um nome de arquivo de texto simples e o salva
            txt_filename = f"resumo_{i+1}.txt"
            txt_path = os.path.join(batch_dir, txt_filename)
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(summary_text)
                
            summary_metadata.append({
                "id": i + 1,
                "title": video_title,
                "channel": channel_title,
                "txt_filename": txt_filename
            })

        # 4. Salva os metadados do lote para referência futura
        with open(os.path.join(batch_dir, '_metadata.json'), 'w', encoding='utf-8') as f:
            json.dump({"summaries": summary_metadata}, f, indent=4)
            
        # 5. Retorna o resultado final da tarefa
        return {'status': 'Concluído', 'batch_id': batch_id, 'summary_count': total_videos}

    except Exception as e:
        # Em caso de erro, atualiza o estado para 'FAILURE'
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        # Também é uma boa prática registrar o erro no log do servidor
        print(f"ERRO na tarefa Celery: {e}")
        # Retorna a exceção para que o Celery a registre como uma falha
        raise e

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/generate-summaries', methods=['POST'])
def handle_generate_summaries():
    data = request.get_json()
    batch_id = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    batch_dir = os.path.join(DATA_DIR, batch_id)
    os.makedirs(batch_dir)

    videos = buscar_videos(data.get('channel', ''), data.get('timeType'), data.get('timeValue'))

    if not videos:
        return jsonify({"status": "success", "batch_id": batch_id, "summary_count": 0})

    summary_metadata = []
    for i, video in enumerate(videos):
        video_id = video['id']['videoId']
        video_title = video['snippet']['title']
        channel_title = video['snippet']['channelTitle']
        
        transcription = obter_transcricao(video_id)
        summary_text = resumir_texto_com_gemini(transcription, video_title, channel_title)
        
        txt_filename = f"resumo_{i+1}.txt"
        txt_path = os.path.join(batch_dir, txt_filename)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(summary_text)
            
        summary_metadata.append({
            "id": i + 1,
            "title": video_title,
            "channel": channel_title,
            "txt_filename": txt_filename
        })

    with open(os.path.join(batch_dir, '_metadata.json'), 'w', encoding='utf-8') as f:
        json.dump({"summaries": summary_metadata}, f, indent=4)
        
    return jsonify({"status": "success", "batch_id": batch_id, "summary_count": len(summary_metadata)})

@app.route('/api/get-overview')
def handle_get_overview():
    batches = []
    if os.path.exists(DATA_DIR):
        for batch_id in sorted(os.listdir(DATA_DIR), reverse=True):
            batch_dir = os.path.join(DATA_DIR, batch_id)
            metadata_path = os.path.join(batch_dir, '_metadata.json')
            if os.path.isdir(batch_dir) and os.path.exists(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    batches.append({
                        "id": batch_id,
                        "date": batch_id.split('_')[0],
                        "time": batch_id.split('_')[1].replace('-', ':'),
                        "summary_count": len(metadata.get("summaries", [])),
                        "summaries_metadata": metadata.get("summaries", [])
                    })
    return jsonify({"batches": batches})

@app.route('/api/generate-consolidated-summary', methods=['POST'])
def handle_generate_consolidated_summary():
    data = request.get_json()
    batch_id = data.get('batch_id')
    batch_dir = os.path.join(DATA_DIR, batch_id)

    if not os.path.exists(batch_dir):
        return jsonify({"error": "Lote não encontrado."}), 404

    all_summaries_text = []
    metadata_path = os.path.join(batch_dir, '_metadata.json')
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    for summary_info in metadata.get("summaries", []):
        txt_path = os.path.join(batch_dir, summary_info['txt_filename'])
        if os.path.exists(txt_path):
            with open(txt_path, 'r', encoding='utf-8') as f_txt:
                all_summaries_text.append(f"--- RESUMO DO VÍDEO: {summary_info['title']} ---\n{f_txt.read()}")

    final_analysis = gerar_analise_consolidada_com_gemini("\n\n".join(all_summaries_text))
    return jsonify({"consolidated_summary": final_analysis})

@app.route('/api/get-summary-content/<batch_id>/<txt_filename>')
def get_summary_content(batch_id, txt_filename):
    try:
        if '..' in batch_id or '..' in txt_filename:
            return jsonify({"error": "Acesso inválido."}), 400
        
        file_path = os.path.join(DATA_DIR, batch_id, txt_filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({"content": content})
        else:
            return jsonify({"error": "Arquivo de resumo não encontrado."}), 404
    except Exception as e:
        print(f"Erro ao ler arquivo de resumo: {e}")
        return jsonify({"error": "Erro interno ao ler arquivo."}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)