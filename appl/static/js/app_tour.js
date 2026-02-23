/**
 * Tour guidato per SunBooking
 * Mostra una guida interattiva al primo accesso su ogni pagina principale
 */

// Configurazione dei tour per ogni pagina
const APP_TOURS = {
    
    // Tour della pagina Calendario
    calendar: [
        {
            target: '.fc-view-harness',
            title: '📅 Il tuo Calendario',
            content: 'Qui vedi tutti gli appuntamenti del giorno. Ogni colonna è associata ad un operatore.',
            position: 'bottom'
        },
        {
            target: '.fc-toolbar',
            title: '⬅️ ➡️ Navigazione',
            content: 'Usa le frecce per cambiare giorno. Clicca sui pulsanti per vedere la settimana o il mese. Clicca "Vai a OGGI" per tornare alla vista del giorno corrente',
            position: 'bottom'
        },
        {
            target: '.fc-timegrid-slot',
            title: '➕ Nuovo Appuntamento',
            content: 'Clicca su uno slot vuoto per creare un nuovo appuntamento. Oppure usa il campo di ricerca cliente in alto a destra sopra il calendario, e poi seleziona il servizio',
            position: 'right'
        }
    ],
    
    // Tour della pagina Pacchetti
    pacchetti: [
        {
            target: '#btnNuovoPacchetto, [data-action="nuovo-pacchetto"], .btn-nuovo-pacchetto',
            title: '📦 Crea un Pacchetto',
            content: 'Clicca qui per creare un nuovo pacchetto di servizi o una carta prepagata per i tuoi clienti.',
            position: 'bottom'
        },
        {
            target: '#pacchetti-table, .pacchetti-list, [data-section="lista-pacchetti"]',
            title: '📋 I tuoi Pacchetti',
            content: 'Qui vedi tutti i pacchetti attivi. Clicca su uno per vedere i dettagli e le sedute rimanenti.',
            position: 'top'
        }
    ],
    
    // Tour della pagina Clienti
    clients: [
        {
            target: '#search-client, .search-box, [data-action="search"]',
            title: '🔍 Cerca Clienti',
            content: 'Digita nome, cognome o telefono per trovare un cliente velocemente.',
            position: 'bottom'
        },
        {
            target: '#btn-add-client, .btn-nuovo-cliente, [data-action="add-client"]',
            title: '➕ Nuovo Cliente',
            content: 'Clicca qui per aggiungere un nuovo cliente all\'anagrafica.',
            position: 'left'
        }
    ],
    
    // Tour della pagina Impostazioni
    settings: [
        {
            target: '.list-group, .settings-menu, nav',
            title: '⚙️ Menu Impostazioni',
            content: 'Da qui puoi configurare operatori, servizi, orari e tutte le funzionalità dell\'app.',
            position: 'right'
        }
    ]
};


/**
 * Mostra il tour guidato per una sezione specifica
 */
function startTour(section) {
    const steps = APP_TOURS[section];
    if (!steps || steps.length === 0) {
        console.log('Nessun tour disponibile per:', section);
        return;
    }
    
    let currentStep = 0;
    
    // Crea il contenitore del tooltip se non esiste
    let tooltip = document.getElementById('tour-tooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'tour-tooltip';
        tooltip.innerHTML = `
            <div class="tour-content">
                <div class="tour-header">
                    <span class="tour-title"></span>
                    <button class="tour-close" onclick="closeTour()">&times;</button>
                </div>
                <div class="tour-body"></div>
                <div class="tour-footer">
                    <span class="tour-progress"></span>
                    <div class="tour-buttons">
                        <button class="tour-btn tour-prev">Indietro</button>
                        <button class="tour-btn tour-next">Avanti</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(tooltip);
        
        // Aggiungi stili CSS
        const style = document.createElement('style');
        style.textContent = `
            #tour-tooltip {
                position: fixed;
                z-index: 99999;
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.3);
                max-width: 320px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            #tour-tooltip.hidden { display: none; }
            .tour-content { padding: 16px; }
            .tour-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            .tour-title {
                font-weight: 600;
                font-size: 16px;
                color: #333;
            }
            .tour-close {
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: #999;
                padding: 0;
                line-height: 1;
            }
            .tour-close:hover { color: #333; }
            .tour-body {
                color: #666;
                font-size: 14px;
                line-height: 1.5;
                margin-bottom: 16px;
            }
            .tour-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .tour-progress {
                font-size: 12px;
                color: #999;
            }
            .tour-buttons { display: flex; gap: 8px; }
            .tour-btn {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                transition: all 0.2s;
            }
            .tour-prev {
                background: #f0f0f0;
                color: #333;
            }
            .tour-prev:hover { background: #e0e0e0; }
            .tour-next {
                background: #0d6efd;
                color: white;
            }
            .tour-next:hover { background: #0b5ed7; }
            .tour-highlight {
                position: relative;
                z-index: 99998;
                box-shadow: 0 0 0 4px rgba(13, 110, 253, 0.5);
                border-radius: 4px;
            }
            .tour-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                z-index: 99997;
            }
        `;
        document.head.appendChild(style);
    }
    
    // Crea overlay
    let overlay = document.getElementById('tour-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'tour-overlay';
        overlay.className = 'tour-overlay';
        document.body.appendChild(overlay);
    }
    overlay.style.display = 'block';
    
    function showStep(index) {
        // Rimuovi highlight precedente
        document.querySelectorAll('.tour-highlight').forEach(el => {
            el.classList.remove('tour-highlight');
        });
        
        const step = steps[index];
        const target = document.querySelector(step.target);
        
        // Aggiorna contenuto tooltip
        tooltip.querySelector('.tour-title').textContent = step.title;
        tooltip.querySelector('.tour-body').textContent = step.content;
        tooltip.querySelector('.tour-progress').textContent = `${index + 1} di ${steps.length}`;
        
        // Gestisci pulsanti
        const prevBtn = tooltip.querySelector('.tour-prev');
        const nextBtn = tooltip.querySelector('.tour-next');
        prevBtn.style.display = index === 0 ? 'none' : 'block';
        nextBtn.textContent = index === steps.length - 1 ? 'Fine' : 'Avanti';
        
        prevBtn.onclick = () => { if (index > 0) showStep(index - 1); };
        nextBtn.onclick = () => {
            if (index < steps.length - 1) {
                showStep(index + 1);
            } else {
                closeTour();
            }
        };
        
        // Posiziona tooltip
        tooltip.classList.remove('hidden');
        
        if (target) {
            target.classList.add('tour-highlight');
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            setTimeout(() => {
                const rect = target.getBoundingClientRect();
                let top, left;
                
                switch (step.position) {
                    case 'bottom':
                        top = rect.bottom + 10;
                        left = rect.left + (rect.width / 2) - 160;
                        break;
                    case 'top':
                        top = rect.top - tooltip.offsetHeight - 10;
                        left = rect.left + (rect.width / 2) - 160;
                        break;
                    case 'left':
                        top = rect.top + (rect.height / 2) - (tooltip.offsetHeight / 2);
                        left = rect.left - tooltip.offsetWidth - 10;
                        break;
                    case 'right':
                        top = rect.top + (rect.height / 2) - (tooltip.offsetHeight / 2);
                        left = rect.right + 10;
                        break;
                    default:
                        top = rect.bottom + 10;
                        left = rect.left;
                }
                
                // Mantieni nel viewport
                left = Math.max(10, Math.min(left, window.innerWidth - 340));
                top = Math.max(10, Math.min(top, window.innerHeight - tooltip.offsetHeight - 10));
                
                tooltip.style.top = top + 'px';
                tooltip.style.left = left + 'px';
            }, 100);
        } else {
            // Se target non trovato, centra il tooltip
            tooltip.style.top = '50%';
            tooltip.style.left = '50%';
            tooltip.style.transform = 'translate(-50%, -50%)';
        }
        
        currentStep = index;
    }
    
    showStep(0);
}


/**
 * Chiude il tour e salva che è stato visto
 */
function closeTour() {
    const tooltip = document.getElementById('tour-tooltip');
    const overlay = document.getElementById('tour-overlay');
    
    if (tooltip) tooltip.classList.add('hidden');
    if (overlay) overlay.style.display = 'none';
    
    document.querySelectorAll('.tour-highlight').forEach(el => {
        el.classList.remove('tour-highlight');
    });
}
window.closeTour = closeTour;


/**
 * Controlla se mostrare il tour automaticamente al primo accesso
 */
function checkAutoTour(section) {
    const storageKey = 'tour_' + section + '_seen';
    const seen = localStorage.getItem(storageKey);
    
    if (!seen) {
        // Aspetta che la pagina sia completamente caricata
        setTimeout(() => {
            // Mostra conferma prima di iniziare
            const conferma = confirm(
                '👋 Benvenuto!\n\n' +
                'Vuoi vedere una breve guida su come usare questa sezione?\n\n' +
                '(Puoi sempre rivederla dal Centro Assistenza)'
            );
            
            if (conferma) {
                startTour(section);
            }
            
            // Salva che l'utente ha visto/rifiutato il tour
            localStorage.setItem(storageKey, 'true');
        }, 1500);
    }
}


/**
 * Resetta un tour specifico (l'utente lo rivedrà)
 */
function resetTour(section) {
    localStorage.removeItem('tour_' + section + '_seen');
}


/**
 * Resetta tutti i tour
 */
function resetAllTours() {
    Object.keys(APP_TOURS).forEach(section => {
        localStorage.removeItem('tour_' + section + '_seen');
    });
}
window.resetAllTours = resetAllTours;