//appl/static/js/settings.js
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('shift-modal');
    const closeBtn = document.querySelector('.close');

    // Funzione per caricare gli operatori
    function loadOperators() {
        fetch('/settings/operators')
            .then(response => response.json())
.then(data => {
    const tableBody = document.getElementById('operators-table').getElementsByTagName('tbody')[0];
    tableBody.innerHTML = ''; // Pulisci la tabella

    data.forEach(operator => {
        const row = document.createElement('tr');
        row.id = `operator-${operator.id}`;

        const tdNome = document.createElement('td');
        tdNome.textContent = operator.user_nome || '';
        const tdCognome = document.createElement('td');
        tdCognome.textContent = operator.user_cognome || '';
        const tdTipo = document.createElement('td');
        tdTipo.textContent = operator.user_tipo || '';

        const tdActions = document.createElement('td');

        const btnEdit = document.createElement('button');
        btnEdit.type = 'button';
        btnEdit.textContent = 'Modifica';
        btnEdit.addEventListener('click', () => editOperator(operator.id));

        const btnShift = document.createElement('button');
        btnShift.type = 'button';
        btnShift.textContent = 'Turni';
        btnShift.addEventListener('click', () => openShiftModal(operator.id));

        const btnDelete = document.createElement('button');
        btnDelete.type = 'button';
        btnDelete.textContent = 'Elimina';
        btnDelete.addEventListener('click', () => deleteOperator(operator.id));

        tdActions.appendChild(btnEdit);
        tdActions.appendChild(btnShift);
        tdActions.appendChild(btnDelete);

        row.appendChild(tdNome);
        row.appendChild(tdCognome);
        row.appendChild(tdTipo);
        row.appendChild(tdActions);

        tableBody.appendChild(row);
    });
})
            .catch(error => console.error('Errore:', error));
    }

    // Carica gli operatori all'avvio
    loadOperators();

    // Gestione del form per aggiungere un operatore
    document.getElementById('add-operator-form').addEventListener('submit', function(event) {
        event.preventDefault();

        const operatorName = document.getElementById('operator-name').value;
        const operatorCognome = document.getElementById('operator-cognome').value;
        const operatorType = document.getElementById('operator-type').value;

        if (!operatorName || !operatorCognome || !operatorType) {
            alert('Tutti i campi sono obbligatori!');
            return; // Interrompe l'esecuzione se un campo è vuoto
        }

        fetch('/settings/operators', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content') 
            },
            body: JSON.stringify({
                user_nome: operatorName,
                user_cognome: operatorCognome,
                user_tipo: operatorType
            }),
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            loadOperators(); // Ricarica la lista degli operatori
        })
        .catch(error => { // PATCH: La parentesi graffa apre il blocco
            console.error('Errore durante l\'aggiunta dell\'operatore:', error);
            alert('Si è verificato un errore. Riprova più tardi.');
        }); // PATCH: La catena .then().catch() finisce qui
    });
});

