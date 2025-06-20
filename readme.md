# vídeoSumma 🤖

**vídeoSumma** é uma aplicação web que utiliza a API do Gemini para gerar resumos detalhados e análises consolidadas de vídeos do YouTube a partir de canais, links ou palavras-chave. 

## Arquitetura

O projeto utiliza uma arquitetura assíncrona para lidar com o processamento de múltiplos vídeos sem travar a interface do usuário. Os componentes são:
* **Frontend**: HTML, CSS, JavaScript.
* **Backend**: Servidor web com Flask em Python.
* **Fila de Tarefas**: Celery, para processar os resumos em segundo plano.
* **Mensageiro/Cache**: Redis, para a comunicação entre o Flask e o Celery.

## Pré-requisitos

Antes de começar, garanta que você tenha os seguintes softwares instalados:
* Python 3.8+
* pip
* Docker

## Instalação

1.  **Clone o Repositório**
    ```bash
    git clone https://github.com/Kaiky1007/videoSumma
    cd videoSumma/
    ```

2.  **Crie o Arquivo de Ambiente (`.env`)**
    Crie um arquivo chamado `.env` na raiz do projeto e adicione suas chaves de API:
    ```env
    YOUTUBE_API_KEY="SUA_CHAVE_DO_YOUTUBE_AQUI"
    GEMINI_API_KEY="SUA_CHAVE_DO_GEMINI_AQUI"
    ```

3.  **Instale as Dependências Python**
    É recomendado usar um ambiente virtual (`venv`).
    ```bash
    python -m venv venv
    source venv/bin/activate  # No Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

## Como Executar

Para rodar a aplicação completa, você precisará de **3 terminais** abertos na pasta do projeto. Execute os comandos na seguinte ordem:

**1. No Terminal 1: Inicie o Redis com Docker**
(Este comando só precisa ser executado uma vez. O contêiner continuará rodando em segundo plano).
```bash
docker run -d -p 6379:6379 --name resumidor-redis redis
```

**2. No Terminal 2: Inicie o Worker do Celery**
Este terminal ficará ativo, mostrando os logs das tarefas que estão sendo processadas.
```bash
celery -A app.celery worker --loglevel=info
```

**3. No Terminal 3: Inicie o Servidor Flask**
Este terminal ficará ativo, mostrando os logs das requisições web.
```bash
python app.py
```

**4.**
Abra seu navegador e acesse: `http://127.0.0.1:5000`

---
