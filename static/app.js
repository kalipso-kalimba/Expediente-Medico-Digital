function showToast(message, type) {
  type = type || 'info';
  var container = document.getElementById('toast-container');
  if (!container) return;
  var toast = document.createElement('div');
  toast.className = 'toast toast-' + type;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(function () {
    toast.classList.add('toast-out');
    setTimeout(function () { toast.remove(); }, 300);
  }, 4000);
}

(function initTheme() {
  var html = document.documentElement;
  var stored = localStorage.getItem('theme');
  if (!stored) stored = 'light';
  html.setAttribute('data-theme', stored);
})();

document.addEventListener('click', function (e) {
  var toggle = e.target.closest('[data-theme-toggle]');
  if (!toggle) return;
  var html = document.documentElement;
  var current = html.getAttribute('data-theme');
  var next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  try { document.cookie = 'theme=' + next + ';path=/;max-age=31536000;SameSite=Lax'; } catch (e) {}
  showToast(next === 'dark' ? 'Modo oscuro activado' : 'Modo claro activado', 'info');
});

document.querySelectorAll('[data-toggle]').forEach(function (group) {
  var target = document.getElementById(group.dataset.toggle);
  function update() {
    var selected = group.querySelector('input:checked');
    target.classList.toggle('show', selected && selected.value === 'Si');
    target.querySelectorAll('input, textarea, select').forEach(function (field) {
      field.required = Boolean(selected && selected.value === 'Si');
    });
  }
  group.querySelectorAll('input').forEach(function (input) { input.addEventListener('change', update); });
  update();
});

document.getElementById('patientForm')?.addEventListener('submit', function (event) {
  var selectedLicenses = document.querySelectorAll('input[name="license_types"]:checked');
  if (!selectedLicenses.length) {
    event.preventDefault();
    showToast('Seleccione al menos un tipo de licencia.', 'error');
  }
});

document.querySelectorAll('[data-copy]').forEach(function (button) {
  button.addEventListener('click', async function () {
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      button.textContent = 'Copiado';
      showToast('Enlace copiado al portapapeles', 'success');
    } catch (e) {
      prompt('Copie este enlace:', button.dataset.copy);
    }
  });
});

document.querySelectorAll('[data-share]').forEach(function (button) {
  button.addEventListener('click', async function () {
    var url = button.dataset.share;
    if (navigator.share) {
      await navigator.share({ title: 'Expediente Medico Digital', url: url });
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      button.textContent = 'Enlace copiado';
      showToast('Enlace copiado al portapapeles', 'success');
    } catch (e) {
      prompt('Copie este enlace:', url);
    }
  });
});

document.querySelectorAll('[data-confirm]').forEach(function (form) {
  form.addEventListener('submit', function (event) {
    if (!confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});

document.querySelectorAll('[data-toast]').forEach(function (el) {
  var msg = el.dataset.toast;
  if (msg) showToast(msg, el.dataset.toastType || 'info');
});

var nationality = document.getElementById('nationality');
var idType = document.getElementById('idType');
var identification = document.getElementById('identification');
var fullName = document.getElementById('fullName');
var tseLookupBox = document.getElementById('tseLookupBox');
var tseLookupButton = document.getElementById('tseLookupButton');
var tseLookupMessage = document.getElementById('tseLookupMessage');

function normalizeCedula(value) { return value.replace(/\D/g, ''); }
function shouldShowTseLookup() {
  var national = nationality?.value?.toLowerCase().includes('costarricense');
  return Boolean(national && idType?.value === 'cedula');
}
function updateTseLookup() {
  if (!tseLookupBox) return;
  tseLookupBox.classList.toggle('hidden', !shouldShowTseLookup());
}

nationality?.addEventListener('change', function () {
  if (nationality.value === 'Extranjero') idType.value = 'dimex';
  if (nationality.value === 'Costarricense') idType.value = 'cedula';
  updateTseLookup();
});
idType?.addEventListener('change', updateTseLookup);
updateTseLookup();

tseLookupButton?.addEventListener('click', async function () {
  if (!shouldShowTseLookup()) return;
  var cedula = normalizeCedula(identification.value);
  if (!/^\d{9}$/.test(cedula)) {
    tseLookupMessage.textContent = 'Digite una cedula nacional valida de 9 digitos. Puede escribirla con o sin guiones.';
    return;
  }
  tseLookupButton.disabled = true;
  tseLookupMessage.textContent = 'Consultando datos...';
  try {
    var response = await fetch('/api/tse/cedula/' + encodeURIComponent(cedula));
    var payload = await response.json();
    if (payload.success && payload.full_name) {
      fullName.value = payload.full_name;
      tseLookupMessage.textContent = 'Nombre completado automaticamente. Revise que sea correcto antes de enviar.';
    } else {
      tseLookupMessage.textContent = payload.message || 'No fue posible completar los datos automaticamente. Por favor escriba su nombre manualmente.';
    }
  } catch (err) {
    tseLookupMessage.textContent = 'No fue posible completar los datos automaticamente. Por favor escriba su nombre manualmente.';
  } finally {
    tseLookupButton.disabled = false;
  }
});

var provinceSelect = document.getElementById('provinceSelect');
var cantonSelect = document.getElementById('cantonSelect');
var localitySelect = document.getElementById('localitySelect');
var localityInput = document.getElementById('localityInput');
var provinceCode = document.getElementById('provinceCode');
var cantonCode = document.getElementById('cantonCode');
var localityCode = document.getElementById('localityCode');

function setOptions(select, items, placeholder) {
  select.innerHTML = '';
  var empty = document.createElement('option');
  empty.value = '';
  empty.textContent = placeholder;
  select.appendChild(empty);
  items.forEach(function (item) {
    var option = document.createElement('option');
    option.value = item.name;
    option.dataset.code = item.code || item.name;
    option.textContent = item.name;
    select.appendChild(option);
  });
}

function selectedCode(select) { return select?.selectedOptions?.[0]?.dataset?.code || ''; }
async function loadLocationItems(url) {
  var response = await fetch(url);
  if (!response.ok) return [];
  var payload = await response.json();
  return payload.items || [];
}

function resetLocality() {
  setOptions(localitySelect, [], 'Seleccione distrito, barrio o localidad');
  localitySelect.disabled = true;
  localitySelect.classList.remove('hidden');
  localitySelect.name = 'district_or_locality';
  localityInput.disabled = true;
  localityInput.classList.add('hidden');
  localityInput.value = '';
  localityCode.value = '';
}

function resetCanton() {
  setOptions(cantonSelect, [], 'Seleccione canton');
  cantonSelect.disabled = true;
  cantonCode.value = '';
  resetLocality();
}

if (provinceSelect && cantonSelect && localitySelect) {
  loadLocationItems('/api/locations/provinces').then(function (items) { setOptions(provinceSelect, items, 'Seleccione provincia'); });

  provinceSelect.addEventListener('change', async function () {
    provinceCode.value = selectedCode(provinceSelect);
    resetCanton();
    if (!provinceCode.value) return;
    var items = await loadLocationItems('/api/locations/cantons?province_code=' + encodeURIComponent(provinceCode.value));
    setOptions(cantonSelect, items, 'Seleccione canton');
    cantonSelect.disabled = false;
  });

  cantonSelect.addEventListener('change', async function () {
    cantonCode.value = selectedCode(cantonSelect);
    resetLocality();
    if (!provinceCode.value || !cantonCode.value) return;
    var items = await loadLocationItems('/api/locations/districts?province_code=' + encodeURIComponent(provinceCode.value) + '&canton_code=' + encodeURIComponent(cantonCode.value));
    if (items.length) {
      setOptions(localitySelect, items, 'Seleccione distrito, barrio o localidad');
      localitySelect.disabled = false;
    } else {
      localitySelect.disabled = true;
      localitySelect.classList.add('hidden');
      localitySelect.name = '';
      localityInput.disabled = false;
      localityInput.classList.remove('hidden');
    }
  });

  localitySelect.addEventListener('change', function () {
    localityCode.value = selectedCode(localitySelect);
  });
}
