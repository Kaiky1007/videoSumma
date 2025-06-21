# vídeoSumma 🤖

**vídeoSumma** é uma aplicação web que utiliza a API do Gemini para gerar resumos detalhados e análises consolidadas de vídeos do YouTube a partir de canais, links ou palavras-chave. 

## Arquitetura

O projeto utiliza uma arquitetura assíncrona para lidar com o processamento de múltiplos vídeos sem travar a interface do usuário. Os componentes são:
* **Frontend**: HTML, CSS, JavaScript.
* **Backend**: Servidor web com Flask em Python.
* **Fila de Tarefas**: Celery, para processar os resumos em segundo plano.
* **Mensageiro/Cache**: Redis, para a comunicação entre o Flask e o Celery.
* **Contêineres**: Docker e Docker Compose para orquestrar todos os serviços de forma simples e consistente.

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


## Como Executar

1.  **Abra um terminal** na pasta raiz do seu projeto.

2.  **Execute o Docker Compose:**
    ```bash
    docker-compose up --build
    ```
    * `--build`: Esta flag é necessária na primeira vez que você executa, ou sempre que fizer alterações no `Dockerfile` ou no `requirements.txt`. Ela instrui o Docker a construir a imagem da sua aplicação.
    * Nas vezes seguintes, você pode usar apenas `docker-compose up`.

3.  **Acesse a Aplicação:**
    Abra seu navegador e acesse: `http://127.0.0.1:5000`

---
