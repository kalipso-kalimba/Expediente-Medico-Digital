document.querySelectorAll('[data-toggle]').forEach((group) => {
  const target = document.getElementById(group.dataset.toggle);
  const update = () => {
    const selected = group.querySelector('input:checked');
    target.classList.toggle('show', selected && selected.value === 'Si');
    target.querySelectorAll('input, textarea, select').forEach((field) => {
      field.required = Boolean(selected && selected.value === 'Si');
    });
  };
  group.querySelectorAll('input').forEach((input) => input.addEventListener('change', update));
  update();
});

document.getElementById('patientForm')?.addEventListener('submit', (event) => {
  const selectedLicenses = document.querySelectorAll('input[name="license_types"]:checked');
  if (!selectedLicenses.length) {
    event.preventDefault();
    alert('Seleccione al menos un tipo de licencia.');
  }
});

document.querySelectorAll('[data-copy]').forEach((button) => {
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      button.textContent = 'Copiado';
    } catch {
      prompt('Copie este enlace:', button.dataset.copy);
    }
  });
});

document.querySelectorAll('[data-share]').forEach((button) => {
  button.addEventListener('click', async () => {
    const url = button.dataset.share;
    if (navigator.share) {
      await navigator.share({ title: 'Expediente Medico Digital', url });
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      button.textContent = 'Enlace copiado';
    } catch {
      prompt('Copie este enlace:', url);
    }
  });
});

document.querySelectorAll('[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});

const nationality = document.getElementById('nationality');
const idType = document.getElementById('idType');
const identification = document.getElementById('identification');
const fullName = document.getElementById('fullName');
const tseLookupBox = document.getElementById('tseLookupBox');
const tseLookupButton = document.getElementById('tseLookupButton');
const tseLookupMessage = document.getElementById('tseLookupMessage');

const normalizeCedula = (value) => value.replace(/\D/g, '');
const shouldShowTseLookup = () => {
  const national = nationality?.value?.toLowerCase().includes('costarricense');
  return Boolean(national && idType?.value === 'cedula');
};
const updateTseLookup = () => {
  if (!tseLookupBox) return;
  tseLookupBox.classList.toggle('hidden', !shouldShowTseLookup());
};

nationality?.addEventListener('change', () => {
  if (nationality.value === 'Extranjero') idType.value = 'dimex';
  if (nationality.value === 'Costarricense') idType.value = 'cedula';
  updateTseLookup();
});
idType?.addEventListener('change', updateTseLookup);
updateTseLookup();

tseLookupButton?.addEventListener('click', async () => {
  if (!shouldShowTseLookup()) return;
  const cedula = normalizeCedula(identification.value);
  if (!/^\d{9}$/.test(cedula)) {
    tseLookupMessage.textContent = 'Digite una cedula nacional valida de 9 digitos. Puede escribirla con o sin guiones.';
    return;
  }
  tseLookupButton.disabled = true;
  tseLookupMessage.textContent = 'Consultando datos...';
  try {
    const response = await fetch(`/api/tse/cedula/${encodeURIComponent(cedula)}`);
    const payload = await response.json();
    if (payload.success && payload.full_name) {
      fullName.value = payload.full_name;
      tseLookupMessage.textContent = 'Nombre completado automaticamente. Revise que sea correcto antes de enviar.';
    } else {
      tseLookupMessage.textContent = payload.message || 'No fue posible completar los datos automaticamente. Por favor escriba su nombre manualmente.';
    }
  } catch {
    tseLookupMessage.textContent = 'No fue posible completar los datos automaticamente. Por favor escriba su nombre manualmente.';
  } finally {
    tseLookupButton.disabled = false;
  }
});

const provinceSelect = document.getElementById('provinceSelect');
const cantonSelect = document.getElementById('cantonSelect');
const localitySelect = document.getElementById('localitySelect');
const localityInput = document.getElementById('localityInput');
const provinceCode = document.getElementById('provinceCode');
const cantonCode = document.getElementById('cantonCode');
const localityCode = document.getElementById('localityCode');

const setOptions = (select, items, placeholder) => {
  select.innerHTML = '';
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = placeholder;
  select.appendChild(empty);
  items.forEach((item) => {
    const option = document.createElement('option');
    option.value = item.name;
    option.dataset.code = item.code || item.name;
    option.textContent = item.name;
    select.appendChild(option);
  });
};

const selectedCode = (select) => select?.selectedOptions?.[0]?.dataset?.code || '';
const loadLocationItems = async (url) => {
  const response = await fetch(url);
  if (!response.ok) return [];
  const payload = await response.json();
  return payload.items || [];
};

const resetLocality = () => {
  setOptions(localitySelect, [], 'Seleccione distrito, barrio o localidad');
  localitySelect.disabled = true;
  localitySelect.classList.remove('hidden');
  localitySelect.name = 'district_or_locality';
  localityInput.disabled = true;
  localityInput.classList.add('hidden');
  localityInput.value = '';
  localityCode.value = '';
};

const resetCanton = () => {
  setOptions(cantonSelect, [], 'Seleccione canton');
  cantonSelect.disabled = true;
  cantonCode.value = '';
  resetLocality();
};

if (provinceSelect && cantonSelect && localitySelect) {
  loadLocationItems('/api/locations/provinces').then((items) => setOptions(provinceSelect, items, 'Seleccione provincia'));

  provinceSelect.addEventListener('change', async () => {
    provinceCode.value = selectedCode(provinceSelect);
    resetCanton();
    if (!provinceCode.value) return;
    const items = await loadLocationItems(`/api/locations/cantons?province_code=${encodeURIComponent(provinceCode.value)}`);
    setOptions(cantonSelect, items, 'Seleccione canton');
    cantonSelect.disabled = false;
  });

  cantonSelect.addEventListener('change', async () => {
    cantonCode.value = selectedCode(cantonSelect);
    resetLocality();
    if (!provinceCode.value || !cantonCode.value) return;
    const items = await loadLocationItems(`/api/locations/districts?province_code=${encodeURIComponent(provinceCode.value)}&canton_code=${encodeURIComponent(cantonCode.value)}`);
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

  localitySelect.addEventListener('change', () => {
    localityCode.value = selectedCode(localitySelect);
  });
}
