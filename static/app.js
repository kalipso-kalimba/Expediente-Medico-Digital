(function() {
  // --- Progress bar ---
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');

  function updateProgress() {
    const form = document.getElementById('patientForm');
    if (!form || !progressFill) return;
    const fields = form.querySelectorAll('input, select, textarea');
    let total = 0;
    let completed = 0;
    fields.forEach(function(f) {
      if (f.disabled || f.type === 'hidden' || f.type === 'submit' || f.type === 'button') return;
      if (f.closest('.conditional') && !f.closest('.conditional.show')) return;
      total++;
      if (f.type === 'checkbox' || f.type === 'radio') {
        const name = f.name;
        if (name === 'license_types') {
          if (form.querySelectorAll('input[name="license_types"]:checked').length > 0) {
            if (f === form.querySelector('input[name="license_types"]:first-child')) completed++;
          }
          return;
        }
        if (form.querySelector('input[name="' + name + '"]:checked')) {
          if (f === form.querySelector('input[name="' + name + '"]:first-child')) completed++;
        }
        return;
      }
      if (f.value && f.value.trim() !== '') completed++;
    });
    const pct = total === 0 ? 0 : Math.round((completed / total) * 100);
    progressFill.style.width = Math.min(pct, 100) + '%';
    if (progressText) progressText.textContent = pct + '% completado';
  }

  document.addEventListener('change', updateProgress);
  document.addEventListener('input', updateProgress);
  setTimeout(updateProgress, 500);

  // --- Conditional toggles ---
  document.querySelectorAll('[data-toggle]').forEach(function(group) {
    const targetId = group.dataset.toggle;
    const target = document.getElementById(targetId);
    if (!target) return;
    function update() {
      const selected = group.querySelector('input:checked');
      const isSi = Boolean(selected && selected.value === 'Si');
      target.classList.toggle('show', isSi);
      target.querySelectorAll('input, textarea, select').forEach(function(field) {
        const isConditionalReq = field.classList.contains('conditional-required');
        if (isConditionalReq) {
          field.required = isSi;
        } else {
          field.required = Boolean(selected && selected.value === 'Si');
        }
      });
      updateProgress();
    }
    group.querySelectorAll('input').forEach(function(input) {
      input.addEventListener('change', update);
    });
    update();
  });

  // --- License types validation ---
  document.getElementById('patientForm')?.addEventListener('submit', function(event) {
    const selectedLicenses = document.querySelectorAll('input[name="license_types"]:checked');
    if (!selectedLicenses.length) {
      event.preventDefault();
      alert('Seleccione al menos un tipo de licencia.');
      return;
    }
    const missing = getMissingRequiredFields();
    if (missing.length > 0) {
      event.preventDefault();
      showValidationSummary(missing);
    }
  });

  // --- Pre-submit validation ---
  function getMissingRequiredFields() {
    const form = document.getElementById('patientForm');
    if (!form) return [];
    const labels = {
      nationality: 'Nacionalidad',
      id_type: 'Tipo de identificaci\u00f3n',
      identification: 'N\u00famero de c\u00e9dula o DIMEX',
      full_name: 'Nombre completo',
      whatsapp: 'WhatsApp',
      email: 'Email',
      age: 'Edad',
      birth_date: 'Fecha de nacimiento',
      civil_status: 'Estado civil',
      profession: 'Profesi\u00f3n u oficio',
      province: 'Provincia',
      canton: 'Cant\u00f3n',
      district_or_locality: 'Distrito, barrio o localidad',
      exact_address: 'Otras se\u00f1as exactas',
      organ_donor: 'Donador de \u00f3rganos',
      has_illness: 'Padece alguna enfermedad',
      illnesses: 'Enfermedades que padece',
      treatments: 'Medicamentos o tratamientos',
      smokes: 'Fuma',
      smoke_frequency: 'Frecuencia de fumado',
      smoke_product: 'Producto que fuma',
      drinks: 'Toma licor',
      drink_frequency: 'Frecuencia de consumo de licor',
      uses_drugs: 'Consume drogas',
      drug_type: 'Tipo de droga',
      drug_frequency: 'Frecuencia de consumo de drogas',
      weight: 'Peso',
      height: 'Estatura',
      uses_glasses: 'Usa lentes',
      glasses_use: 'Uso de lentes',
      laterality: 'Lateralidad',
      license_types: 'Tipo de licencia',
      truth_declaration: 'Declaraci\u00f3n de veracidad',
      cedula_front: 'Fotograf\u00eda frontal del documento',
      cedula_back: 'Fotograf\u00eda trasera del documento',
    };
    const missing = [];
    const requiredFields = form.querySelectorAll('input[required], select[required], textarea[required]');
    requiredFields.forEach(function(field) {
      if (field.disabled || field.type === 'hidden') return;
      if (field.closest('.conditional') && !field.closest('.conditional.show')) return;
      const name = field.name;
      if (field.type === 'checkbox' || field.type === 'radio') {
        if (name === 'license_types') return;
        const group = form.querySelectorAll('input[name="' + name + '"]');
        let checked = false;
        group.forEach(function(cb) { if (cb.checked) checked = true; });
        if (!checked) {
          missing.push(labels[name] || name);
        }
        return;
      }
      if (field.type === 'file') {
        if (!field.files || field.files.length === 0) {
          missing.push(labels[name] || name);
        }
        return;
      }
      if (!field.value || field.value.trim() === '') {
        missing.push(labels[name] || name);
      }
    });
    const licenseSelected = document.querySelectorAll('input[name="license_types"]:checked').length > 0;
    if (!licenseSelected) missing.push(labels['license_types'] || 'Tipo de licencia');
    return missing;
  }

  function showValidationSummary(missing) {
    const summary = document.getElementById('validationSummary');
    const list = document.getElementById('validationList');
    if (!summary || !list) return;
    list.innerHTML = '';
    missing.forEach(function(item) {
      const li = document.createElement('li');
      li.textContent = item;
      list.appendChild(li);
    });
    summary.classList.remove('hidden');
    summary.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  // --- Copy to clipboard ---
  document.querySelectorAll('[data-copy]').forEach(function(button) {
    button.addEventListener('click', async function() {
      try {
        await navigator.clipboard.writeText(button.dataset.copy);
        button.textContent = 'Copiado';
      } catch {
        prompt('Copie este enlace:', button.dataset.copy);
      }
    });
  });

  // --- Share ---
  document.querySelectorAll('[data-share]').forEach(function(button) {
    button.addEventListener('click', async function() {
      const url = button.dataset.share;
      if (navigator.share) {
        await navigator.share({ title: 'Expediente Medico Digital', url: url });
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

  // --- Confirm dialogs ---
  document.querySelectorAll('[data-confirm]').forEach(function(form) {
    form.addEventListener('submit', function(event) {
      if (!confirm(form.dataset.confirm)) {
        event.preventDefault();
      }
    });
  });

  // --- TSE lookup ---
  const nationality = document.getElementById('nationality');
  const idType = document.getElementById('idType');
  const identification = document.getElementById('identification');
  const fullName = document.getElementById('fullName');
  const tseLookupBox = document.getElementById('tseLookupBox');
  const tseLookupButton = document.getElementById('tseLookupButton');
  const tseLookupMessage = document.getElementById('tseLookupMessage');

  function normalizeCedula(value) { return value.replace(/\D/g, ''); }

  function shouldShowTseLookup() {
    const national = nationality?.value?.toLowerCase().includes('costarricense');
    return Boolean(national && idType?.value === 'cedula');
  }

  function updateTseLookup() {
    if (!tseLookupBox) return;
    tseLookupBox.classList.toggle('hidden', !shouldShowTseLookup());
  }

  nationality?.addEventListener('change', function() {
    if (nationality.value === 'Extranjero') idType.value = 'dimex';
    if (nationality.value === 'Costarricense') idType.value = 'cedula';
    updateTseLookup();
  });
  idType?.addEventListener('change', updateTseLookup);
  updateTseLookup();

  tseLookupButton?.addEventListener('click', async function() {
    if (!shouldShowTseLookup()) return;
    const cedula = normalizeCedula(identification.value);
    if (!/^\d{9}$/.test(cedula)) {
      tseLookupMessage.textContent = 'Digite una c\u00e9dula nacional v\u00e1lida de 9 d\u00edgitos. Puede escribirla con o sin guiones.';
      return;
    }
    tseLookupButton.disabled = true;
    tseLookupMessage.textContent = 'Consultando datos...';
    try {
      const response = await fetch('/api/tse/cedula/' + encodeURIComponent(cedula));
      const payload = await response.json();
      if (payload.success && payload.full_name) {
        fullName.value = payload.full_name;
        tseLookupMessage.textContent = 'Nombre completado autom\u00e1ticamente. Revise que sea correcto antes de enviar.';
      } else {
        tseLookupMessage.textContent = payload.message || 'No fue posible completar los datos autom\u00e1ticamente. Por favor escriba su nombre manualmente.';
      }
    } catch {
      tseLookupMessage.textContent = 'No fue posible completar los datos autom\u00e1ticamente. Por favor escriba su nombre manualmente.';
    } finally {
      tseLookupButton.disabled = false;
    }
  });

  // --- Location selects ---
  const provinceSelect = document.getElementById('provinceSelect');
  const cantonSelect = document.getElementById('cantonSelect');
  const localitySelect = document.getElementById('localitySelect');
  const localityInput = document.getElementById('localityInput');
  const provinceCode = document.getElementById('provinceCode');
  const cantonCode = document.getElementById('cantonCode');
  const localityCode = document.getElementById('localityCode');

  function setOptions(select, items, placeholder) {
    select.innerHTML = '';
    var empty = document.createElement('option');
    empty.value = '';
    empty.textContent = placeholder;
    select.appendChild(empty);
    items.forEach(function(item) {
      var option = document.createElement('option');
      option.value = item.name;
      option.dataset.code = item.code || item.name;
      option.textContent = item.name;
      select.appendChild(option);
    });
  }

  function selectedCode(select) {
    return select?.selectedOptions?.[0]?.dataset?.code || '';
  }

  async function loadLocationItems(url) {
    try {
      var response = await fetch(url);
      if (!response.ok) return [];
      var payload = await response.json();
      return payload.items || [];
    } catch { return []; }
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
    setOptions(cantonSelect, [], 'Seleccione cant\u00f3n');
    cantonSelect.disabled = true;
    cantonCode.value = '';
    resetLocality();
  }

  if (provinceSelect && cantonSelect && localitySelect) {
    loadLocationItems('/api/locations/provinces').then(function(items) {
      setOptions(provinceSelect, items, 'Seleccione provincia');
    });

    provinceSelect.addEventListener('change', async function() {
      provinceCode.value = selectedCode(provinceSelect);
      resetCanton();
      if (!provinceCode.value) return;
      var items = await loadLocationItems('/api/locations/cantons?province_code=' + encodeURIComponent(provinceCode.value));
      setOptions(cantonSelect, items, 'Seleccione cant\u00f3n');
      cantonSelect.disabled = false;
    });

    cantonSelect.addEventListener('change', async function() {
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

    localitySelect.addEventListener('change', function() {
      localityCode.value = selectedCode(localitySelect);
    });
  }
})();
