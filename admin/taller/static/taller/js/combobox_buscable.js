// Combobox con búsqueda en vivo sobre un <select> nativo ya renderizado
// por Django (que sigue siendo la fuente de verdad: valor, validación de
// opciones elegibles y el nombre que se envía al form). El <select> se
// oculta y se reemplaza visualmente por un input de texto + una lista
// desplegable propia, sin dependencias externas.
//
// Uso: iniciarComboboxBuscable(document.getElementById('id_trabajo'), {
//     placeholder: 'Buscar por número o cliente...',
// });
//
// Reutilizable en cualquier <select> con opciones de texto (Trabajo en
// Pagos, Gasto/repuesto en Repuestos usados): la búsqueda compara contra
// el texto visible de cada <option>, así que no hace falta adaptar nada
// por caso de uso más que el placeholder.
function iniciarComboboxBuscable(select, opciones) {
    if (!select || select.dataset.comboboxBuscableInit) { return; }
    select.dataset.comboboxBuscableInit = '1';

    opciones = opciones || {};
    var placeholder = opciones.placeholder || 'Buscar...';

    var idOriginal = select.id;
    if (idOriginal) { select.id = idOriginal + '-select-oculto'; }
    select.hidden = true;

    var wrapper = document.createElement('div');
    wrapper.className = 'combobox-buscable';
    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'form-control combobox-buscable-input';
    input.autocomplete = 'off';
    input.placeholder = placeholder;
    if (idOriginal) { input.id = idOriginal; }
    wrapper.appendChild(input);

    var lista = document.createElement('ul');
    lista.className = 'combobox-buscable-lista';
    lista.hidden = true;
    wrapper.appendChild(lista);

    var activo = -1;

    function normalizar(texto) {
        return (texto || '')
            .toString()
            .normalize('NFD')
            .replace(/[̀-ͯ]/g, '')
            .toLowerCase();
    }

    function opcionesDisponibles() {
        return Array.prototype.slice.call(select.options).filter(function (opt) {
            return opt.value !== '' && !opt.hidden;
        });
    }

    function sincronizarInputConSelect() {
        var seleccionado = select.options[select.selectedIndex];
        input.value = (seleccionado && seleccionado.value) ? seleccionado.textContent.trim() : '';
    }

    function cerrar() {
        lista.hidden = true;
        activo = -1;
        sincronizarInputConSelect();
    }

    function marcarActivo(indice) {
        var items = lista.querySelectorAll('.combobox-buscable-item');
        items.forEach(function (item, i) {
            item.classList.toggle('combobox-buscable-item-activo', i === indice);
        });
        if (items[indice]) { items[indice].scrollIntoView({ block: 'nearest' }); }
    }

    function elegir(opt) {
        select.value = opt.value;
        select.dispatchEvent(new Event('change'));
        lista.hidden = true;
        activo = -1;
    }

    function renderizar(filtro) {
        lista.innerHTML = '';
        var normalizado = normalizar(filtro);
        var visibles = opcionesDisponibles().filter(function (opt) {
            return normalizado === '' || normalizar(opt.textContent).indexOf(normalizado) !== -1;
        });

        if (!visibles.length) {
            var vacio = document.createElement('li');
            vacio.className = 'combobox-buscable-vacio';
            vacio.textContent = 'Sin resultados';
            lista.appendChild(vacio);
        } else {
            visibles.forEach(function (opt) {
                var item = document.createElement('li');
                item.className = 'combobox-buscable-item';
                item.textContent = opt.textContent.trim();
                item.setAttribute('data-value', opt.value);
                // mousedown (no click): dispara antes del blur del input,
                // así la selección no se pierde por cerrarse la lista antes.
                item.addEventListener('mousedown', function (event) {
                    event.preventDefault();
                    elegir(opt);
                });
                lista.appendChild(item);
            });
        }
        activo = -1;
        lista.hidden = false;
        ubicarLista();
    }

    // Por default la lista se abre hacia abajo. Si no entra entre el
    // input y el borde inferior de la ventana (pantalla chica, escalado
    // de Windows, input cerca del fondo del form), y arriba hay más
    // lugar, se abre hacia arriba en su lugar — así nunca queda cortada.
    function ubicarLista() {
        var rectInput = input.getBoundingClientRect();
        var espacioAbajo = window.innerHeight - rectInput.bottom;
        var espacioArriba = rectInput.top;
        var alturaLista = lista.offsetHeight;
        var abrirArriba = alturaLista > espacioAbajo && espacioArriba > espacioAbajo;
        lista.classList.toggle('combobox-buscable-lista-arriba', abrirArriba);
    }

    input.addEventListener('input', function () {
        select.value = '';
        renderizar(input.value);
    });

    input.addEventListener('focus', function () {
        renderizar(input.value);
    });

    // El input puede seguir enfocado después de elegir una opción (Enter
    // no le saca el foco): sin esto, un click posterior sobre el mismo
    // input no dispara 'focus' de nuevo y la lista no vuelve a abrirse.
    input.addEventListener('click', function () {
        if (lista.hidden) { renderizar(input.value); }
    });

    input.addEventListener('blur', function () {
        window.setTimeout(cerrar, 100);
    });

    input.addEventListener('keydown', function (event) {
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            if (lista.hidden) { renderizar(input.value); return; }
            var totalItems = lista.querySelectorAll('.combobox-buscable-item').length;
            if (!totalItems) { return; }
            activo = Math.min(activo + 1, totalItems - 1);
            marcarActivo(activo);
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            if (lista.hidden) { return; }
            activo = Math.max(activo - 1, 0);
            marcarActivo(activo);
        } else if (event.key === 'Enter') {
            if (!lista.hidden && activo >= 0) {
                var items = lista.querySelectorAll('.combobox-buscable-item');
                if (items[activo]) {
                    event.preventDefault();
                    var valor = items[activo].getAttribute('data-value');
                    var opt = opcionesDisponibles().filter(function (o) { return o.value === valor; })[0];
                    if (opt) { elegir(opt); }
                }
            }
        } else if (event.key === 'Escape') {
            cerrar();
        }
    });

    select.addEventListener('change', sincronizarInputConSelect);
    sincronizarInputConSelect();
}
