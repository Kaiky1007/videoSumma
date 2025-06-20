// Gerencia a interação do usuário com as opções de período de tempo.
document.querySelectorAll('.time-option').forEach(option => {
    option.addEventListener('click', function() {
        document.querySelectorAll('.time-option').forEach(opt => opt.classList.remove('active'));
        this.classList.add('active');
        this.querySelector('input[type="radio"]').checked = true;
        
        const input = this.querySelector('input[type="number"]');
        if (input) input.focus();
    });
});

// Manipula a submissão do formulário de configuração.
document.getElementById('config-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const timeTypeRadio = document.querySelector('input[name="time-type"]:checked');
    if (!timeTypeRadio) {
        alert('Por favor, selecione um período de busca.');
        return;
    }
    
    const timeType = timeTypeRadio.value;
    const timeValue = document.getElementById(timeType + '-input').value;
    if (!timeValue) {
        alert('Por favor, informe a quantidade de ' + (timeType === 'hours' ? 'horas' : 'semanas') + '.');
        return;
    }
    
    const channel = document.getElementById('channel-input').value;

    // Exibe o spinner de carregamento e desabilita o botão.
    document.getElementById('loading-spinner').style.display = 'block';
    document.querySelector('button[type="submit"]').disabled = true;
    
    // Faz a chamada para a API do backend.
    fetch('/api/summarize', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            timeType: timeType,
            timeValue: timeValue,
            channel: channel
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('A resposta do servidor não foi bem-sucedida.');
        }
        return response.json();
    })
    .then(summaries => {
        displaySummaries(summaries, timeType, timeValue);
    })
    .catch(error => {
        console.error('Erro ao buscar resumos:', error);
        alert('Ocorreu um erro ao comunicar com o servidor. Verifique o console para mais detalhes.');
    })
    .finally(() => {
        // Esconde o spinner e reabilita o botão, independentemente do resultado.
        document.getElementById('loading-spinner').style.display = 'none';
        document.querySelector('button[type="submit"]').disabled = false;
    });
});

// Exibe os resumos recebidos do backend, renderizando o Markdown.
function displaySummaries(summaries, timeType, timeValue) {
    const container = document.getElementById('summaries-container');
    const subtitle = document.getElementById('summary-subtitle');
    const noResultsDiv = document.getElementById('no-results');
    
    const period = timeType === 'hours' ? `${timeValue} horas` : `${timeValue} semanas`;
    subtitle.textContent = `${summaries.length} resumos encontrados para vídeos nas últimas ${period}.`;
    
    container.innerHTML = '';
    
    if (summaries.length === 0) {
        noResultsDiv.style.display = 'block';
    } else {
        noResultsDiv.style.display = 'none';
        summaries.forEach(video => {
            const videoCard = document.createElement('div');
            videoCard.className = 'video-card';

            // Converte o texto do resumo de Markdown para HTML
            const rawHtml = marked.parse(video.summary);

            // Limpa o HTML para segurança antes de inseri-lo na página
            const sanitizedHtml = DOMPurify.sanitize(rawHtml);

            videoCard.innerHTML = `
                <h5 class="video-title">${video.title}</h5>
                <p class="text-muted mb-2">
                    <i class="fas fa-tv me-1"></i>${video.channel}
                </p>
                <div class="video-summary">
                    ${sanitizedHtml}
                </div>
            `;
            container.appendChild(videoCard);
        });
    }
    
    document.getElementById('config-screen').style.display = 'none';
    document.getElementById('summary-screen').style.display = 'block';
}

// Controla o botão "Voltar" para retornar à tela de configuração.
function goBack() {
    document.getElementById('summary-screen').style.display = 'none';
    document.getElementById('config-screen').style.display = 'block';
}

let currentVideos = [];
        
// Gerenciamento de telas
function showScreen(screenName) {
    // Esconde todas as telas
    document.querySelectorAll('[id$="-screen"]').forEach(screen => {
        screen.style.display = 'none';
    });
    
    // Remove active de todos os botões
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Mostra a tela selecionada
    if (screenName === 'config') {
        document.getElementById('config-screen').style.display = 'block';
        document.querySelector('[onclick="showScreen(\'config\')"]').classList.add('active');
    } else if (screenName === 'overview') {
        document.getElementById('overview-screen').style.display = 'block';
        document.querySelector('[onclick="showScreen(\'overview\')"]').classList.add('active');
        updateOverviewStats();
        loadPDFs();
    }
}