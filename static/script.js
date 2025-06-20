function showScreen(screenName) {
    document.querySelectorAll('.main-container').forEach(s => s.style.display = 'none');
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

    const screenElement = document.getElementById(`${screenName}-screen`);
    const activeBtn = document.querySelector(`.nav-btn[onclick="showScreen('${screenName}')"]`);

    if (screenElement) screenElement.style.display = 'block';
    if (activeBtn) activeBtn.classList.add('active');

    if (screenName === 'overview') {
        loadOverviewData();
    }
}

document.getElementById('config-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const loadingSpinner = form.querySelector('.loading-spinner');
    const statusText = loadingSpinner.querySelector('p');

    const timeTypeRadio = form.querySelector('input[name="time-type"]:checked');
    if (!timeTypeRadio) { return alert('Por favor, selecione um período de busca.'); }
    
    const timeValue = document.getElementById(timeTypeRadio.value + '-input').value;
    if (!timeValue) { return alert('Por favor, informe a quantidade.'); }

    loadingSpinner.style.display = 'block';
    submitBtn.disabled = true;
    statusText.textContent = "Enviando seu pedido para a fila de processamento...";

    fetch('/api/generate-summaries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            timeType: timeTypeRadio.value,
            timeValue: timeValue,
            channel: form.querySelector('#channel-input').value
        })
    })
    .then(response => {
        if (response.status !== 202) {
            throw new Error('Falha ao iniciar a tarefa no servidor.');
        }
        return response.json();
    })
    .then(data => {
        if (data.task_id) {
            checkTaskStatus(data.task_id);
        } else {
            throw new Error('O servidor não retornou um ID para a tarefa.');
        }
    })
    .catch(error => {
        console.error('Erro ao iniciar a geração de resumos:', error);
        alert(`Erro: ${error.message}`);
        loadingSpinner.style.display = 'none';
        submitBtn.disabled = false;
    });
});

function checkTaskStatus(taskId) {
    const loadingSpinner = document.querySelector('.loading-spinner');
    const submitBtn = document.querySelector('button[type="submit"]');
    const statusText = loadingSpinner.querySelector('p');

    const interval = setInterval(() => {
        fetch(`/api/task-status/${taskId}`)
            .then(response => response.json())
            .then(data => {
                if (data.status) {
                    statusText.textContent = data.status;
                }
                if (data.state === 'SUCCESS') {
                    clearInterval(interval);
                    loadingSpinner.style.display = 'none';
                    submitBtn.disabled = false;
                    alert(`Processamento concluído! ${data.result.summary_count} resumos foram gerados.`);
                    showScreen('overview');
                } 
                else if (data.state === 'FAILURE') {
                    clearInterval(interval);
                    loadingSpinner.style.display = 'none';
                    submitBtn.disabled = false;
                    alert(`Ocorreu um erro durante o processamento: ${data.status}`);
                }
            })
            .catch(err => {
                clearInterval(interval);
                alert('Erro de conexão ao verificar o status da tarefa.');
                console.error('Erro de polling:', err);
                loadingSpinner.style.display = 'none';
                submitBtn.disabled = false;
            });
    }, 5000);
}

async function loadOverviewData() {
    const selector = document.getElementById('batch-selector');
    const overviewContent = document.getElementById('overview-content');
    const noBatchesDiv = document.getElementById('no-batches');
    
    selector.innerHTML = '<option>Carregando lotes...</option>';
    
    try {
        const response = await fetch('/api/get-overview');
        const data = await response.json();
        
        if (data.batches && data.batches.length > 0) {
            overviewContent.style.display = 'block';
            noBatchesDiv.style.display = 'none';
            selector.innerHTML = '';
            data.batches.forEach(batch => {
                const option = document.createElement('option');
                option.value = batch.id;
                option.textContent = `Lote de ${batch.date} às ${batch.time} (${batch.summary_count} resumos)`;
                option.dataset.summaries = JSON.stringify(batch.summaries_metadata);
                selector.appendChild(option);
            });
            displayBatchDetails(selector.value);
        } else {
            overviewContent.style.display = 'none';
            noBatchesDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Erro ao carregar dados da visão geral:', error);
        noBatchesDiv.innerHTML = '<p class="text-danger">Não foi possível carregar os lotes.</p>';
    }
}

document.getElementById('batch-selector').addEventListener('change', function(e) {
    displayBatchDetails(e.target.value);
})

function displayBatchDetails(batchId) {
    const selector = document.getElementById('batch-selector');
    const selectedOption = selector.querySelector(`option[value="${batchId}"]`);
    if (!selectedOption) return;

    const summaries = JSON.parse(selectedOption.dataset.summaries || '[]');
    const accordionContainer = document.getElementById('summaries-accordion-container');
    const generalSummaryContainer = document.getElementById('general-summary-content');

    generalSummaryContainer.innerHTML = '<p class="text-muted">Clique em "Gerar Análise" para começar.</p>';
    accordionContainer.innerHTML = '';

    if (summaries.length === 0) {
        accordionContainer.innerHTML = '<p class="text-muted">Este lote não contém resumos.</p>';
        return;
    }

    summaries.forEach((summary, index) => {
        const accordionId = `accordion-${batchId}-${index}`;
        const accordionItem = document.createElement('div');
        accordionItem.className = 'accordion-item';
        accordionItem.innerHTML = `
            <h2 class="accordion-header" id="heading-${accordionId}">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" 
                        data-bs-target="#collapse-${accordionId}" aria-expanded="false" 
                        aria-controls="collapse-${accordionId}">
                    <strong>${summary.title}</strong>&nbsp;-&nbsp;<small class="text-muted">${summary.channel}</small>
                </button>
            </h2>
            <div id="collapse-${accordionId}" class="accordion-collapse collapse" 
                 aria-labelledby="heading-${accordionId}">
                <div class="accordion-body">
                    <div class="text-center">
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="visually-hidden">Carregando...</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        const button = accordionItem.querySelector('button');
        button.addEventListener('click', () => {
            loadSummaryContent(batchId, summary.txt_filename, `collapse-${accordionId}`);
        }, { once: true });

        accordionContainer.appendChild(accordionItem);
    });
}

async function loadSummaryContent(batchId, txtFilename, targetDivId) {
    const accordionBody = document.getElementById(targetDivId).querySelector('.accordion-body');
    try {
        const response = await fetch(`/api/get-summary-content/${batchId}/${txtFilename}`);
        const data = await response.json();

        if (data.error) throw new Error(data.error);
        
        const rawHtml = marked.parse(data.content);
        accordionBody.innerHTML = DOMPurify.sanitize(rawHtml);
    } catch (error) {
        console.error('Erro ao carregar conteúdo do resumo:', error);
        accordionBody.innerHTML = `<p class="text-danger">Não foi possível carregar o resumo.</p>`;
    }
}

document.getElementById('generate-summary-btn').addEventListener('click', async function() {
    const btn = this;
    const batchId = document.getElementById('batch-selector').value;
    const container = document.getElementById('general-summary-content');

    if (!batchId) return alert('Selecione um lote primeiro.');

    btn.disabled = true;
    container.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Gerando...</span></div>';

    try {
        const response = await fetch('/api/generate-consolidated-summary', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ batch_id: batchId })
        });
        const data = await response.json();
        
        if (data.error) throw new Error(data.error);

        const rawHtml = marked.parse(data.consolidated_summary);
        container.innerHTML = DOMPurify.sanitize(rawHtml);
    } catch (error) {
        console.error('Erro ao gerar resumo consolidado:', error);
        container.innerHTML = `<p class="text-danger">Erro ao gerar análise: ${error.message}</p>`;
    } finally {
        btn.disabled = false;
    }
});

document.addEventListener('DOMContentLoaded', () => showScreen('config'));
