# REQUISITOS DEL PROYECTO - SISTEMA WEB PARA FORMULARIOS MÉDICOS

## 1. Objetivo general

Quiero crear un programa web para uso médico, cuyo objetivo sea facilitar la recopilación de información de los pacientes antes de una consulta, valoración o dictamen médico.

La idea es que el médico pueda generar y enviar un enlace personalizado a cada paciente. Al abrir ese enlace, el paciente ingresará a un sitio web donde iniciará una interacción guiada, respondiendo una serie de preguntas previamente definidas por el médico.

El sistema debe estar diseñado como una aplicación web segura, moderna, responsive y fácil de usar, tanto para el médico como para el paciente.

---

## 2. Inicio de la interacción con el paciente

La interacción debe iniciar solicitándole al paciente su número de cédula o DIMEX.

Si el paciente es nacional y digita una cédula costarricense válida, el sistema deberá intentar, de ser técnicamente posible y legalmente permitido, consultar la información pública disponible en el sitio del Tribunal Supremo de Elecciones / Registro Civil:

https://servicioselectorales.tse.go.cr/chc/consulta_cedula.aspx

El objetivo de esta consulta sería completar automáticamente los datos personales básicos del paciente, como nombre completo y otros datos disponibles públicamente, evitando que el paciente tenga que escribirlos manualmente.

Esta función deberá implementarse únicamente si es viable, estable y permitida por el sitio consultado. No se debe romper ningún mecanismo de seguridad, captcha, restricción técnica o política de uso del sitio. Si no existe una API oficial o el sitio no permite automatización, el sistema deberá permitir que el paciente complete los datos manualmente.

---

## 3. Manejo de expediente digital del paciente

A partir del número de cédula o DIMEX, el sistema deberá verificar si ya existe una carpeta o expediente digital asociado a ese paciente.

Cada paciente deberá tener una única carpeta principal de expediente, nombrada con el siguiente formato:

```text
Nombre del paciente - número de cédula o DIMEX
```

Ejemplo:

```text
Juan Pérez Rodríguez - 1-1234-0567
```

Si esa carpeta no existe, el sistema deberá crearla automáticamente.

Si esa carpeta ya existe, el sistema no deberá crear una carpeta duplicada. En ese caso, deberá utilizar la carpeta existente del paciente.

Dentro de la carpeta del paciente, el sistema deberá guardar cada nuevo documento de atención generado a partir de la interacción con el paciente.

Cada documento de atención deberá nombrarse con el siguiente formato:

```text
Fecha actual - nombre del paciente - número de cédula o DIMEX
```

Ejemplo:

```text
2026-05-18 - Juan Pérez Rodríguez - 1-1234-0567.pdf
```

---

## 4. Estructura esperada de almacenamiento

La estructura de almacenamiento deberá ser similar a esta:

```text
Expedientes/
└── Juan Pérez Rodríguez - 1-1234-0567/
    ├── 2026-05-18 - Juan Pérez Rodríguez - 1-1234-0567.pdf
    ├── 2026-05-18 - cedula-frontal - Juan Pérez Rodríguez - 1-1234-0567.jpg
    ├── 2026-05-18 - cedula-trasera - Juan Pérez Rodríguez - 1-1234-0567.jpg
    ├── 2026-06-02 - Juan Pérez Rodríguez - 1-1234-0567.pdf
    ├── 2026-06-02 - cedula-frontal - Juan Pérez Rodríguez - 1-1234-0567.jpg
    └── 2026-06-02 - cedula-trasera - Juan Pérez Rodríguez - 1-1234-0567.jpg
```

---

## 5. Informe PDF del paciente

El informe de cada paciente, es decir, el archivo nombrado con el formato:

```text
2026-05-18 - Juan Pérez Rodríguez - 1-1234-0567.pdf
```

deberá generarse en formato PDF, usando una plantilla genérica que el sistema deberá construir automáticamente.

Una vez que el paciente complete todas las preguntas, el sistema deberá generar automáticamente un formulario completo con toda la información recopilada. Ese formulario deberá guardarse como un nuevo documento PDF dentro de la carpeta correspondiente del paciente.

El médico deberá poder revisar, descargar, imprimir o guardar ese documento como parte del expediente clínico o administrativo del paciente.

---

## 6. Requisitos funcionales del sistema

1. Panel privado para el médico.
2. Creación o selección de formularios con preguntas preestablecidas.
3. Generación de enlaces únicos para cada paciente.
4. Inicio de la interacción solicitando el número de cédula o DIMEX del paciente.
5. Validación del formato de cédula costarricense o DIMEX.
6. Consulta automática al TSE / Registro Civil para completar datos personales, únicamente si es técnica y legalmente posible.
7. Opción de completar los datos manualmente si la consulta automática no está disponible.
8. Verificación automática de si el paciente ya tiene una carpeta de expediente creada.
9. Creación automática de la carpeta del paciente si no existe.
10. Uso de la carpeta existente si el paciente ya tiene expediente abierto.
11. Creación de un nuevo documento de atención por cada interacción completada.
12. Nombramiento automático de la carpeta con el formato: nombre del paciente - número de cédula o DIMEX.
13. Nombramiento automático de cada documento con el formato: fecha actual - nombre del paciente - número de cédula o DIMEX.
14. Generación del informe final en PDF usando una plantilla genérica construida por el sistema.
15. Solicitud y carga de fotografía frontal y trasera de la cédula o DIMEX del paciente.
16. Posibilidad de cargar las fotografías desde archivos guardados o tomarlas directamente desde la cámara del teléfono celular.
17. Interfaz sencilla para que el paciente responda desde celular o computadora.
18. Validación de respuestas obligatorias.
19. Preguntas condicionales según respuestas Sí / No.
20. Guardado seguro de la información.
21. Protección de datos personales y médicos.
22. Diseño responsive, limpio y fácil de usar.
23. Declaración obligatoria de que la información proporcionada por el paciente es correcta, completa y verdadera.

---

## 7. Preguntas del formulario

El formulario deberá contener las siguientes preguntas.

### 7.1 Datos generales

1. Nacionalidad.
2. Tipo de identificación:
   - Cédula nacional.
   - DIMEX.
3. Número de cédula o DIMEX.
4. Nombre completo.
5. Número de WhatsApp.
6. Email.
7. Edad.
8. Fecha de nacimiento.
9. Estado civil.
10. Profesión u oficio.
11. Provincia.
12. Cantón.
13. Distrito y otras señas.
14. Donador de órganos:
   - Indicar si dona órganos en caso de accidente grave.
15. Declaración de veracidad:
   - El paciente deberá aceptar una declaración indicando que la información proporcionada es correcta, completa y verdadera.

### 7.2 Datos médicos

1. Enfermedades:
   - Respuesta: Sí / No.
   - Si responde Sí, indicar cuál o cuáles enfermedades padece.
   - Luego indicar cuáles medicamentos o tratamientos utiliza actualmente para esa enfermedad o enfermedades.

2. Fuma:
   - Respuesta: Sí / No.
   - Si responde Sí, indicar cuántas veces a la semana fuma.
   - Indicar qué tipo de producto fuma.

3. Toma licor:
   - Respuesta: Sí / No.
   - Si responde Sí, indicar cuántas bebidas alcohólicas consume al día o por semana.

4. Consume drogas:
   - Respuesta: Sí / No.
   - Si responde Sí, indicar qué tipo de droga consume.
   - Indicar con qué frecuencia la consume.

5. Peso.

6. Estatura.

7. Usa lentes por discapacidad visual:
   - Respuesta: Sí / No.
   - Si responde Sí, indicar si los usa para ver de cerca, de lejos o para ambos.

8. Lateralidad:
   - Indicar si es derecho o zurdo.

9. Tipo de licencia que necesita:
   - Opciones: A, B, C, D o E.
   - El paciente debe poder seleccionar más de una opción si necesita varios tipos de licencia.
   - Ejemplo: A y B.

---

## 8. Fotografías de cédula o DIMEX

Durante la interacción, el sistema deberá solicitar al paciente una fotografía de su documento de identificación.

El paciente deberá poder cargar:

1. Fotografía frontal de la cédula o DIMEX.
2. Fotografía trasera de la cédula o DIMEX.

El sistema deberá permitir cargar estas fotografías de dos formas:

1. Seleccionando una imagen previamente guardada en el dispositivo.
2. Tomando la fotografía directamente desde la cámara del teléfono celular, cuando el paciente esté usando un dispositivo móvil.

La interfaz para cargar las fotografías debe ser sencilla, clara y compatible con celulares.

El sistema deberá mostrar instrucciones al paciente, por ejemplo:

- Tome una fotografía clara de la parte frontal de su cédula o DIMEX.
- Tome una fotografía clara de la parte trasera de su cédula o DIMEX.
- Verifique que la imagen no esté borrosa.
- Verifique que los datos sean legibles.
- Evite reflejos, sombras fuertes o cortes en la imagen.

Las fotografías deberán almacenarse de forma segura dentro del expediente digital del paciente o asociadas al documento de atención correspondiente.

El sistema debe validar que ambas imágenes hayan sido cargadas antes de permitir finalizar el formulario, salvo que el médico configure esta carga como opcional.

Por seguridad, las imágenes de la cédula o DIMEX no deben guardarse en una carpeta pública. Deben almacenarse en una ubicación privada, protegida y accesible únicamente para el médico autorizado desde el panel privado del sistema.

---

## 9. Comportamiento de las preguntas Sí / No

Las preguntas que la web le plantee al paciente deben estar diseñadas para facilitar al máximo la interacción, especialmente desde celular.

En la medida de lo posible, las preguntas de respuesta Sí / No deberán mostrarse mediante controles tipo checkbox, switch, botón seleccionable o selector visual, para que el paciente pueda responder de forma rápida y sencilla sin tener que escribir manualmente.

Ejemplos:

```text
¿Padece alguna enfermedad?
[ ] Sí
[ ] No

¿Fuma?
[ ] Sí
[ ] No

¿Toma licor?
[ ] Sí
[ ] No

¿Consume drogas?
[ ] Sí
[ ] No

¿Usa lentes por discapacidad visual?
[ ] Sí
[ ] No

¿Dona órganos en caso de accidente grave?
[ ] Sí
[ ] No
```

El formulario debe funcionar como una interacción guiada y condicional, no como una lista plana de preguntas.

Cuando una pregunta tenga respuesta Sí / No, el sistema debe evaluar la respuesta del paciente y, según corresponda, mostrar la siguiente pregunta relacionada para ampliar o completar esa información.

Ejemplo:

Pregunta:

```text
¿Padece alguna enfermedad?
[ ] Sí
[ ] No
```

Si el paciente marca “No”:

- El sistema debe continuar con la siguiente sección o pregunta general.

Si el paciente marca “Sí”:

- El sistema debe mostrar inmediatamente una pregunta adicional:
  - “¿Cuál o cuáles enfermedades padece?”

Después de que el paciente escriba la enfermedad o enfermedades, el sistema debe mostrar otra pregunta relacionada:

```text
¿Qué medicamentos o tratamientos utiliza actualmente para esa enfermedad?
```

Ejemplo de flujo:

1. ¿Padece alguna enfermedad?
   - Sí / No.
2. Si responde Sí:
   - ¿Cuál o cuáles enfermedades padece?
3. Luego:
   - ¿Qué medicamentos o tratamientos utiliza actualmente para esa enfermedad?
4. Una vez completada esa información:
   - El sistema continúa con la siguiente pregunta del formulario.

Este mismo comportamiento debe aplicarse a las demás preguntas condicionales.

Ejemplos:

### Fuma

- Si responde No: continuar.
- Si responde Sí: preguntar cuántas veces fuma a la semana y qué tipo de producto fuma.

### Toma licor

- Si responde No: continuar.
- Si responde Sí: preguntar cuántas bebidas alcohólicas consume al día o por semana.

### Consume drogas

- Si responde No: continuar.
- Si responde Sí: preguntar qué tipo de droga consume y con qué frecuencia.

### Usa lentes por discapacidad visual

- Si responde No: continuar.
- Si responde Sí: preguntar si los usa para ver de cerca, de lejos o para ambos.

### Dona órganos en caso de accidente grave

- Si responde No: continuar.
- Si responde Sí: guardar esa respuesta como afirmativa dentro del formulario final.

El objetivo es que el paciente avance paso a paso, respondiendo solo las preguntas que realmente correspondan según sus respuestas anteriores.

El sistema debe evitar mostrar desde el inicio todos los campos secundarios. Los campos de aclaración o ampliación solo deben aparecer cuando la respuesta del paciente los haga necesarios.

Esto hará que el formulario sea más limpio, más fácil de usar y menos confuso, especialmente para pacientes que lo completen desde un teléfono celular.

También se debe cuidar que los botones, checkboxes o switches sean grandes, visibles y fáciles de seleccionar en pantallas táctiles.

---

## 10. Plantilla del informe PDF

El informe generado para cada paciente deberá crearse en formato PDF.

El sistema deberá construir una plantilla genérica para ese PDF, con diseño claro, ordenado y profesional, que incluya toda la información recolectada durante la interacción con el paciente.

La plantilla PDF deberá contener, como mínimo:

1. Encabezado del documento.
2. Nombre del médico o clínica, si está disponible.
3. Fecha y hora de generación del informe.
4. Datos generales del paciente.
5. Datos médicos del paciente.
6. Tipo de licencia solicitada.
7. Respuestas condicionales completadas por el paciente.
8. Declaración de que la información proporcionada es correcta, completa y verdadera.
9. Registro de aceptación de la declaración por parte del paciente.
10. Referencia a las fotografías frontal y trasera de la cédula o DIMEX cargadas por el paciente.
11. Espacio o sección para observaciones del médico, si se desea agregar posteriormente.
12. Código interno del documento o expediente, si el sistema lo genera.

---

## 11. Resultado final esperado

Al finalizar la interacción, el sistema deberá:

1. Guardar todos los datos recopilados.
2. Crear o actualizar el expediente digital del paciente.
3. Crear un nuevo documento de atención dentro de la carpeta del paciente.
4. Generar un PDF con el formulario completado.
5. Nombrar correctamente el archivo generado.
6. Guardar las fotografías frontal y trasera de la cédula o DIMEX.
7. Asociar las fotografías al documento de atención correspondiente.
8. Dejar el documento disponible para revisión del médico.
9. Permitir descargar o imprimir el documento.
10. Registrar fecha y hora de finalización.
11. Registrar que el paciente aceptó la declaración de veracidad.

---

## 12. Seguridad y privacidad

El sistema trabajará con datos personales y médicos sensibles, por lo que debe diseñarse con buenas prácticas de seguridad, privacidad, control de acceso, validación de datos, almacenamiento seguro y cumplimiento normativo.

Debe considerar como mínimo:

1. HTTPS obligatorio.
2. Acceso privado para el médico.
3. Enlaces únicos y difíciles de adivinar.
4. Enlaces con vencimiento configurable.
5. Validación de datos en frontend y backend.
6. Protección contra CSRF, XSS e inyección SQL.
7. Almacenamiento privado de documentos.
8. Almacenamiento privado de fotografías de cédula o DIMEX.
9. No exponer datos médicos sensibles en la URL.
10. No exponer fotografías ni PDFs en carpetas públicas.
11. Control de permisos.
12. Registro de accesos.
13. Manejo seguro de archivos PDF e imágenes.
14. Validación del tipo, tamaño y formato de los archivos cargados.
15. Respaldos seguros.
16. Declaración de veracidad aceptada por el paciente.
17. Aviso sobre el tratamiento de datos personales y médicos.

---

## 13. Objetivo de la primera versión

El objetivo es desarrollar una primera versión funcional del sistema, priorizando seguridad, facilidad de uso y una estructura que luego pueda ampliarse con más funciones.

La primera versión debería permitir:

1. Crear o usar un formulario médico preestablecido.
2. Generar un enlace para el paciente.
3. Permitir que el paciente complete el formulario desde celular o computadora.
4. Usar preguntas dinámicas y condicionales.
5. Solicitar fotografía frontal y trasera de la cédula o DIMEX.
6. Permitir tomar las fotografías desde la cámara del teléfono.
7. Crear la carpeta del expediente si no existe.
8. Reutilizar la carpeta existente si el paciente ya tiene expediente.
9. Crear un nuevo documento PDF por cada atención.
10. Guardar el documento dentro de la carpeta del paciente.
11. Guardar las fotografías de identificación asociadas a la atención.
12. Permitir que el médico revise y descargue el documento generado.

---

## 14. Tecnología sugerida

Se puede desarrollar usando una tecnología moderna, segura y fácil de mantener.

Opciones sugeridas:

- Backend: Laravel, Django, FastAPI, Node.js o similar.
- Frontend: HTML, CSS, JavaScript, React, Vue o Blade si se usa Laravel.
- Base de datos: MySQL, PostgreSQL o SQLite para una primera versión.
- Generación de PDF: librería confiable del backend.
- Manejo de archivos: almacenamiento privado con validación de imágenes y PDFs.
- Diseño responsive para celulares, tabletas y computadoras.
- Panel privado para administración médica.

El desarrollador puede recomendar la mejor arquitectura según la complejidad y el alcance de la primera versión.

---

## 15. Instrucciones para OpenCode

Analizar este documento como especificación inicial del proyecto.

Antes de generar código, proponer:

1. Arquitectura recomendada.
2. Tecnologías exactas a utilizar.
3. Estructura de carpetas.
4. Modelo de base de datos.
5. Flujo del paciente.
6. Flujo del médico.
7. Estrategia para generación de PDF.
8. Estrategia para almacenamiento seguro de imágenes y documentos.
9. Riesgos técnicos, legales o de seguridad.
10. Primera versión mínima funcional.

No implementar automatización contra el sitio del TSE si no existe una forma técnica y legalmente segura de hacerlo. En ese caso, dejar el flujo manual como opción principal.
