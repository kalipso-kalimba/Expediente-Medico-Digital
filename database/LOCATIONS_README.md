# Base local de ubicaciones de Costa Rica

El archivo `costa_rica_locations.json` contiene una copia local de provincias, cantones y distritos de Costa Rica para evitar consultas externas durante el llenado del formulario del paciente.

Fuente utilizada para esta primera version: `https://ubicaciones.paginasweb.cr/`.

La estructura oficial estable cubierta es Provincia -> Canton -> Distrito. En el formulario, el distrito se usa dentro del campo unificado "Distrito, barrio o localidad". Si en el futuro se obtiene una base confiable de barrios o localidades, puede integrarse en esa misma lista sin agregar otro campo al paciente.

Si se obtiene una fuente oficial mas completa en el futuro, se puede actualizar el JSON manteniendo la misma estructura.
