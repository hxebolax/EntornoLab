@echo off
rem ============================================================================
rem  entorno.bat - Administración del proyecto EntornoLab
rem  Crea el entorno virtual, instala dependencias, ejecuta desde código el
rem  Estudio y el reproductor, pasa las pruebas, genera sonidos, ejemplos e
rem  idiomas y compila con cx_Freeze (con los runtimes de Visual C++).
rem
rem  Uso con menú:        entorno.bat
rem  Uso sin menú:        entorno.bat <orden> [argumentos]
rem  Órdenes: crear, instalar, actualizar, ejecutar, depurar, jugar, pruebas,
rem           comprobar, sonidos, ejemplos, idiomas, compilar, compilar-debug,
rem           empaquetar, limpiar, datos, registros, diagnostico, congelar
rem  Ejemplo: entorno.bat jugar data\ejemplos\vivienda-de-ejemplo.elab --alumno ana
rem
rem  Guardar con finales de línea CRLF y codificación UTF-8 SIN BOM.
rem ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

rem ── Configuración ──────────────────────────────────────────────────────────
set "NOMBRE_APP=entornolab"
set "NOMBRE_VISIBLE=EntornoLab"
set "EXE=EntornoLab.exe"
set "EXE_JUGAR=EntornoLabJugar.exe"
rem Versión de Python del proyecto (la de requires-python). Vacía = la
rem predeterminada del lanzador py (la marcada con * en "py -0p"). No se usa
rem "py -3": elegiría la más reciente instalada, quizá una preliminar sin
rem ruedas de wxPython.
set "VERSION_PY=3.15"
set "VENV=%~dp0.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PYW=%VENV%\Scripts\pythonw.exe"
set "SETUP=setup_cx.py"
set "BUILD_DIR=build\%NOMBRE_APP%"
rem Herramientas que generan recursos de data (las dos son opcionales).
set "TOOL_SONIDOS=tools\sintetizar_sonidos.py"
set "TOOL_EJEMPLOS=tools\generar_ejemplos.py"
rem Rueda propia del motor de sonido BASS: basskit recortado, solo bass.dll. La
rem instala requirements.txt desde la carpeta __pip__, que viaja con el código.
set "RUEDA_BASS=__pip__\basskit-0.8.12+reconocedor-py3-none-win_amd64.whl"
rem ──────────────────────────────────────────────────────────────────────────

if not "%~1"=="" goto ORDEN

:MENU
echo.
echo  %NOMBRE_VISIBLE% - Menú de administración
echo  ==============================================
echo  1. Crear o reparar el entorno virtual e instalar dependencias
echo  2. Instalar dependencias
echo  3. Actualizar dependencias a la última versión permitida
echo  4. Ejecutar el Estudio desde el código
echo  5. Ejecutar el Estudio con consola, en modo depuración
echo  6. Ejecutar el reproductor, Jugar, desde el código
echo  7. Ejecutar las pruebas
echo  8. Comprobar el proyecto: estilo, teclas, novedades y arranque
echo  9. Generar los sonidos de serie
echo  10. Generar los entornos de ejemplo
echo  11. Actualizar y compilar los idiomas
echo  12. Compilar con cx_Freeze y empaquetar en ZIP
echo  13. Compilar en modo depuración, con consola
echo  14. Limpiar compilaciones y cachés
echo  15. Abrir la carpeta data
echo  16. Abrir la carpeta de registros
echo  17. Diagnóstico del entorno
echo  18. Guardar las versiones instaladas en requirements-lock.txt
echo  0. Salir
echo.
set "RESTO="
set "OPCION="
set /p "OPCION=Elija una opción y pulse Intro: "
if "%OPCION%"=="1" call :CREAR & goto PAUSA
if "%OPCION%"=="2" call :INSTALAR & goto PAUSA
if "%OPCION%"=="3" call :ACTUALIZAR & goto PAUSA
if "%OPCION%"=="4" call :EJECUTAR & goto PAUSA
if "%OPCION%"=="5" call :DEPURAR & goto PAUSA
if "%OPCION%"=="6" call :JUGAR & goto PAUSA
if "%OPCION%"=="7" call :PRUEBAS & goto PAUSA
if "%OPCION%"=="8" call :COMPROBAR & goto PAUSA
if "%OPCION%"=="9" call :SONIDOS & goto PAUSA
if "%OPCION%"=="10" call :EJEMPLOS & goto PAUSA
if "%OPCION%"=="11" call :IDIOMAS & goto PAUSA
if "%OPCION%"=="12" call :COMPILAR & goto PAUSA
if "%OPCION%"=="13" call :COMPILAR_DEBUG & goto PAUSA
if "%OPCION%"=="14" call :LIMPIAR & goto PAUSA
if "%OPCION%"=="15" call :DATOS & goto PAUSA
if "%OPCION%"=="16" call :REGISTROS & goto PAUSA
if "%OPCION%"=="17" call :DIAGNOSTICO & goto PAUSA
if "%OPCION%"=="18" call :CONGELAR & goto PAUSA
if "%OPCION%"=="0" goto FIN
echo Opción no válida: %OPCION%
goto MENU

:PAUSA
echo.
pause
goto MENU

:ORDEN
set "ORDEN=%~1"
rem Los argumentos que siguen a la orden se guardan entre comillas, uno a uno,
rem para pasarlos tal cual (por ejemplo, a "jugar" o a "pruebas").
set "RESTO="
:RECOGER
shift
if "%~1"=="" goto RECOGIDO
set "RESTO=!RESTO! "%~1""
goto RECOGER
:RECOGIDO
if /i "%ORDEN%"=="crear" call :CREAR & goto SALIR
if /i "%ORDEN%"=="instalar" call :INSTALAR & goto SALIR
if /i "%ORDEN%"=="actualizar" call :ACTUALIZAR & goto SALIR
if /i "%ORDEN%"=="ejecutar" call :EJECUTAR & goto SALIR
if /i "%ORDEN%"=="depurar" call :DEPURAR & goto SALIR
if /i "%ORDEN%"=="jugar" call :JUGAR & goto SALIR
if /i "%ORDEN%"=="pruebas" call :PRUEBAS & goto SALIR
if /i "%ORDEN%"=="comprobar" call :COMPROBAR & goto SALIR
if /i "%ORDEN%"=="sonidos" call :SONIDOS & goto SALIR
if /i "%ORDEN%"=="ejemplos" call :EJEMPLOS & goto SALIR
if /i "%ORDEN%"=="idiomas" call :IDIOMAS & goto SALIR
if /i "%ORDEN%"=="compilar" call :COMPILAR & goto SALIR
if /i "%ORDEN%"=="compilar-debug" call :COMPILAR_DEBUG & goto SALIR
if /i "%ORDEN%"=="empaquetar" call :EMPAQUETAR & goto SALIR
if /i "%ORDEN%"=="limpiar" call :LIMPIAR & goto SALIR
if /i "%ORDEN%"=="datos" call :DATOS & goto SALIR
if /i "%ORDEN%"=="registros" call :REGISTROS & goto SALIR
if /i "%ORDEN%"=="diagnostico" call :DIAGNOSTICO & goto SALIR
if /i "%ORDEN%"=="congelar" call :CONGELAR & goto SALIR
echo Orden desconocida: %ORDEN%
echo Órdenes válidas: crear, instalar, actualizar, ejecutar, depurar, jugar, pruebas,
echo comprobar, sonidos, ejemplos, idiomas, compilar, compilar-debug, empaquetar,
echo limpiar, datos, registros, diagnostico, congelar
exit /b 2

:SALIR
exit /b %ERRORLEVEL%

rem ============================================================================
rem  Subrutinas. Cada una termina con "exit /b <código>" para que el modo sin
rem  menú devuelva un código de salida útil: 0 significa correcto.
rem ============================================================================

:CREAR
echo.
echo === Creando el entorno virtual en %VENV% ===
if exist "%PY%" (
	echo El entorno virtual ya existe; se reutiliza.
) else (
	where py >nul 2>nul
	if not errorlevel 1 (
		if defined VERSION_PY (
			py -%VERSION_PY% -m venv "%VENV%"
			if errorlevel 1 (
				echo ERROR: no está instalado Python %VERSION_PY%. Instálelo con: py install %VERSION_PY%
				echo o desde python.org, y vuelva a intentarlo.
				exit /b 1
			)
		) else (
			py -m venv "%VENV%"
		)
	) else (
		where python >nul 2>nul
		if errorlevel 1 (
			echo ERROR: no se encontró Python. Instale Python de 64 bits desde python.org
			echo marcando la opción de añadirlo al PATH, y vuelva a intentarlo.
			exit /b 1
		)
		python -m venv "%VENV%"
	)
)
if not exist "%PY%" (
	echo ERROR: no se pudo crear el entorno virtual.
	exit /b 1
)
"%PY%" --version
call :INSTALAR
exit /b %ERRORLEVEL%

:INSTALAR
echo.
echo === Instalando dependencias ===
call :COMPROBAR_VENV || exit /b 1
if not exist "%RUEDA_BASS%" (
	echo ERROR: falta %RUEDA_BASS%
	echo Es la rueda del motor de sonido BASS y viaja con el código en la carpeta __pip__.
	echo Recupérela del repositorio y vuelva a intentarlo.
	exit /b 1
)
"%PY%" -m pip install --upgrade pip setuptools wheel
if exist requirements.txt (
	"%PY%" -m pip install -r requirements.txt
	if errorlevel 1 (
		echo ERROR: falló la instalación de requirements.txt.
		exit /b 1
	)
)
rem El motor BASS viene incluido: se comprueba que basskit ha quedado instalado y que carga bass.dll.
"%PY%" -c "from basskit.dlls.bass import bass; v = bass.BASS_GetVersion(); print('BASS', '.'.join(str(v >> d & 255) for d in (24, 16, 8, 0)), 'instalado con basskit.')"
if errorlevel 1 (
	echo ERROR: basskit no ha quedado instalado o no carga bass.dll. Revise los mensajes anteriores.
	exit /b 1
)
if exist requirements-dev.txt (
	"%PY%" -m pip install -r requirements-dev.txt
	if errorlevel 1 (
		echo ERROR: falló la instalación de requirements-dev.txt.
		exit /b 1
	)
)
if exist tools\despues_de_instalar.py "%PY%" tools\despues_de_instalar.py
echo Dependencias instaladas correctamente.
exit /b 0

:ACTUALIZAR
echo.
echo === Actualizando dependencias ===
call :COMPROBAR_VENV || exit /b 1
"%PY%" -m pip install --upgrade pip
if exist requirements.txt "%PY%" -m pip install --upgrade -r requirements.txt || exit /b 1
if exist requirements-dev.txt "%PY%" -m pip install --upgrade -r requirements-dev.txt || exit /b 1
echo Dependencias actualizadas.
exit /b 0

:EJECUTAR
echo.
echo === Ejecutando el Estudio de %NOMBRE_VISIBLE% desde el código ===
call :COMPROBAR_VENV || exit /b 1
rem pythonw no abre consola: es como lo verá el usuario final. Los errores
rem quedan en data\logs y el lector de pantalla no se distrae con una consola.
start "" "%PYW%" main.py !RESTO!
exit /b 0

:DEPURAR
echo.
echo === Ejecutando el Estudio de %NOMBRE_VISIBLE% con consola ===
call :COMPROBAR_VENV || exit /b 1
rem APP_DEPURACION=1 sube el registro a DEBUG y copia los mensajes en esta consola.
set "APP_DEPURACION=1"
"%PY%" -X dev -X faulthandler main.py !RESTO!
set "CODIGO=!ERRORLEVEL!"
set "APP_DEPURACION="
echo La aplicación terminó con el código !CODIGO!.
exit /b !CODIGO!

:JUGAR
echo.
echo === Ejecutando el reproductor de %NOMBRE_VISIBLE% desde el código ===
call :COMPROBAR_VENV || exit /b 1
rem Con consola y esperando a que termine: así se ve su código de salida.
rem Sus mensajes van a data\logs\jugar_*.log.
"%PY%" jugar.py !RESTO!
set "CODIGO=!ERRORLEVEL!"
echo El reproductor terminó con el código !CODIGO!.
exit /b !CODIGO!

:PRUEBAS
echo.
echo === Ejecutando las pruebas ===
call :COMPROBAR_VENV || exit /b 1
if not exist tests (
	echo No hay carpeta tests.
	exit /b 0
)
"%PY%" -m pytest tests -q !RESTO!
if errorlevel 1 (
	echo Hay pruebas que fallan.
	exit /b 1
)
echo Todas las pruebas pasan.
exit /b 0

:COMPROBAR
echo.
echo === Comprobando el proyecto ===
call :COMPROBAR_VENV || exit /b 1
set "FALLOS=0"
echo.
echo Estilo y errores con ruff:
"%PY%" -m ruff check app main.py jugar.py tools setup_cx.py tests
if errorlevel 1 set /a FALLOS+=1
echo.
echo Atajos de teclado frente a la lista de teclas:
"%PY%" tools\comprobar_teclas.py
if errorlevel 1 set /a FALLOS+=1
echo.
echo Notas de la versión:
"%PY%" tools\notas_version.py --salida build\notas_version.md
if errorlevel 1 set /a FALLOS+=1
echo.
echo Cadenas traducibles y estado de los idiomas:
"%PY%" tools\extraer_cadenas.py
if errorlevel 1 set /a FALLOS+=1
"%PY%" tools\informe_traducciones.py
if errorlevel 1 set /a FALLOS+=1
echo.
echo Arranque del Estudio y del reproductor desde el código:
rem La comprobación usa otra carpeta data para no tocar la del desarrollador.
set "APP_DATA_DIR=%~dp0build\comprobacion_data"
"%PY%" main.py --comprobar-arranque
if errorlevel 1 (
	echo ERROR: el Estudio no arrancó bien. Revise build\comprobacion_data\logs.
	set /a FALLOS+=1
) else (
	echo El Estudio arranca y se cierra correctamente.
)
"%PY%" jugar.py --comprobar-arranque
if errorlevel 1 (
	echo ERROR: el reproductor no arrancó bien. Revise build\comprobacion_data\logs.
	set /a FALLOS+=1
) else (
	echo El reproductor arranca y se cierra correctamente.
)
set "APP_DATA_DIR="
if exist "%BUILD_DIR%\%EXE%" (
	call :COMPROBAR_BUILD
	if errorlevel 1 set /a FALLOS+=1
) else (
	echo No hay versión compilada que comprobar.
)
echo.
if not "!FALLOS!"=="0" (
	echo Comprobación terminada con !FALLOS! apartados con problemas.
	exit /b 1
)
echo Comprobación terminada sin problemas.
exit /b 0

:COMPROBAR_BUILD
echo.
echo Arranque de la versión compilada:
if not exist "%BUILD_DIR%\%EXE%" (
	echo No existe %BUILD_DIR%\%EXE%. Compile primero.
	exit /b 1
)
if not exist "%BUILD_DIR%\%EXE_JUGAR%" (
	echo No existe %BUILD_DIR%\%EXE_JUGAR%. Compile primero.
	exit /b 1
)
rem La prueba de humo usa otra carpeta data, fuera de la compilación, para no ensuciar la distribución.
rem Se llena con una copia de la data que viaja (sonidos, idiomas, complementos, ejemplos): así se
rem prueba con los recursos de verdad y no con una carpeta vacía.
if exist "%~dp0build\comprobacion_data" rmdir /s /q "%~dp0build\comprobacion_data"
robocopy "%BUILD_DIR%\data" "%~dp0build\comprobacion_data" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
	echo ERROR: no se pudo copiar la data de la compilación a build\comprobacion_data.
	exit /b 1
)
set "APP_DATA_DIR=%~dp0build\comprobacion_data"
set "CODIGO_BUILD=0"
start "" /wait "%BUILD_DIR%\%EXE%" --comprobar-arranque
if errorlevel 1 (
	echo ERROR: %EXE% no arrancó bien. Revise build\comprobacion_data\logs.
	set "CODIGO_BUILD=1"
) else (
	echo %EXE% arranca y se cierra correctamente.
)
start "" /wait "%BUILD_DIR%\%EXE_JUGAR%" --comprobar-arranque
if errorlevel 1 (
	echo ERROR: %EXE_JUGAR% no arrancó bien. Revise build\comprobacion_data\logs.
	set "CODIGO_BUILD=1"
) else (
	echo %EXE_JUGAR% arranca y se cierra correctamente.
)
set "APP_DATA_DIR="
rem OpenAL con HRTF y BASS, con las bibliotecas y los datos de la compilación, en memoria (sin sonar).
"%PY%" tools\verificar_build.py --motores "%BUILD_DIR%"
if errorlevel 1 (
	echo ERROR: los motores de sonido de la compilación no cargan. Revise los mensajes anteriores.
	set "CODIGO_BUILD=1"
)
rem El reproductor compilado de verdad en modo guion: sin ventana ni sonido, abre un ejemplo con sus
rem complementos y juega un poco con OpenAL (HRTF) y con BASS en memoria. Usa una copia temporal de la data.
"%PY%" tools\verificar_build.py --guion "%BUILD_DIR%"
if errorlevel 1 (
	echo ERROR: el reproductor compilado no supera el modo guion. Revise los mensajes anteriores.
	set "CODIGO_BUILD=1"
)
exit /b !CODIGO_BUILD!

:SONIDOS
echo.
echo === Generando el paquete de sonidos por defecto en data\sounds\por_defecto ===
call :COMPROBAR_VENV || exit /b 1
if not exist "%TOOL_SONIDOS%" (
	echo No existe %TOOL_SONIDOS%; no hay nada que generar.
	exit /b 1
)
"%PY%" "%TOOL_SONIDOS%" !RESTO!
if errorlevel 1 (
	echo ERROR: no se pudieron generar los sonidos.
	exit /b 1
)
echo Sonidos generados.
exit /b 0

:EJEMPLOS
echo.
echo === Generando los entornos de ejemplo en data\ejemplos ===
call :COMPROBAR_VENV || exit /b 1
if not exist "%TOOL_EJEMPLOS%" (
	echo No existe %TOOL_EJEMPLOS%; no hay nada que generar.
	exit /b 1
)
"%PY%" "%TOOL_EJEMPLOS%" !RESTO!
if errorlevel 1 (
	echo ERROR: no se pudieron generar los entornos de ejemplo.
	exit /b 1
)
echo Entornos de ejemplo generados.
exit /b 0

:IDIOMAS
echo.
echo === Idiomas: extraer cadenas, actualizar catálogos y compilar ===
call :COMPROBAR_VENV || exit /b 1
"%PY%" tools\extraer_cadenas.py
if errorlevel 1 (
	echo ERROR: hay cadenas que no se pueden traducir. Corríjalas y repita.
	exit /b 1
)
"%PY%" tools\actualizar_po.py
if errorlevel 1 (
	echo ERROR: no se pudieron actualizar los catálogos.
	exit /b 1
)
"%PY%" tools\compilar_traducciones.py
if errorlevel 1 (
	echo ERROR: hay traducciones con errores; esas entradas se mostrarán en español.
	exit /b 1
)
"%PY%" tools\informe_traducciones.py
echo Para añadir un idioma: "%PY%" tools\actualizar_po.py --nuevo CODIGO
echo Para ver cada cadena pendiente: "%PY%" tools\informe_traducciones.py --detalle
exit /b 0

:COMPILAR
echo.
echo === Compilando %NOMBRE_VISIBLE% con cx_Freeze ===
call :COMPROBAR_VENV || exit /b 1
if not exist "%SETUP%" (
	echo ERROR: no existe %SETUP% en la raíz del proyecto.
	exit /b 1
)
if exist tools\antes_de_compilar.py (
	"%PY%" tools\antes_de_compilar.py || exit /b 1
)
"%PY%" "%SETUP%" build
if errorlevel 1 (
	echo ERROR: la compilación ha fallado. Revise los mensajes anteriores.
	exit /b 1
)
if not exist "%BUILD_DIR%" (
	echo ERROR: no se generó la carpeta %BUILD_DIR%.
	exit /b 1
)
call :COMPROBAR_BUILD
if errorlevel 1 exit /b 1
call :EMPAQUETAR
exit /b %ERRORLEVEL%

:COMPILAR_DEBUG
echo.
echo === Compilando %NOMBRE_VISIBLE% en modo depuración, con consola ===
call :COMPROBAR_VENV || exit /b 1
if exist tools\antes_de_compilar.py (
	"%PY%" tools\antes_de_compilar.py || exit /b 1
)
"%PY%" "%SETUP%" build --debug
if errorlevel 1 (
	echo ERROR: la compilación ha fallado.
	exit /b 1
)
echo Compilación de depuración en %BUILD_DIR%. No la distribuya: muestra consola.
exit /b 0

:EMPAQUETAR
echo.
echo === Empaquetando la distribución: ZIP y version.json ===
call :COMPROBAR_VENV || exit /b 1
if not exist tools\empaquetar.py (
	echo No existe tools\empaquetar.py; la distribución queda en %BUILD_DIR%.
	exit /b 0
)
"%PY%" tools\empaquetar.py
if errorlevel 1 (
	echo ERROR: no se pudo empaquetar la distribución.
	exit /b 1
)
exit /b 0

:LIMPIAR
echo.
echo === Limpiando compilaciones y cachés ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist .pytest_cache rmdir /s /q .pytest_cache
if exist .ruff_cache rmdir /s /q .ruff_cache
if exist htmlcov rmdir /s /q htmlcov
rem Borra los __pycache__ del proyecto, pero no los del entorno virtual.
for /d /r . %%D in (__pycache__) do if exist "%%D" (
	set "RUTA=%%D"
	if "!RUTA:\.venv\=!"=="!RUTA!" if "!RUTA:\venv\=!"=="!RUTA!" rmdir /s /q "%%D"
)
echo Limpieza terminada. El entorno virtual y la carpeta data no se tocan.
exit /b 0

:DATOS
if not exist data mkdir data
start "" explorer "%~dp0data"
exit /b 0

:REGISTROS
if not exist data\logs mkdir data\logs
start "" explorer "%~dp0data\logs"
exit /b 0

:DIAGNOSTICO
echo.
echo === Diagnóstico del entorno ===
where py >nul 2>nul && py -0p
if exist "%PY%" (
	echo Python del entorno virtual:
	"%PY%" -c "import sys, platform; print(sys.version); print(platform.platform())"
	"%PY%" -c "import wx; print('wxPython', wx.version())" 2>nul || echo wxPython no está instalado.
	"%PY%" -c "import pygame; print('pygame-ce', pygame.version.ver, 'SDL', pygame.version.SDL)" 2>nul || echo pygame-ce no está instalado.
	"%PY%" -c "import numpy; print('numpy', numpy.__version__)" 2>nul || echo numpy no está instalado.
	"%PY%" -c "import sounddevice; print('sounddevice', sounddevice.__version__)" 2>nul || echo sounddevice no está instalado.
	"%PY%" -c "import cryptography; print('cryptography', cryptography.__version__)" 2>nul || echo cryptography no está instalado.
	"%PY%" -c "import basskit; from basskit.dlls.bass import bass; v = bass.BASS_GetVersion(); print('basskit', basskit.__version__, 'con BASS', '.'.join(str(v >> d & 255) for d in (24, 16, 8, 0)))" 2>nul || echo basskit no está instalado o no carga bass.dll: sin motor de sonido BASS. Use la opción 2.
	"%PY%" -c "import cx_Freeze; print('cx_Freeze', cx_Freeze.__version__)" 2>nul || echo cx_Freeze no está instalado.
	"%PY%" -m pip check
) else (
	echo El entorno virtual no existe todavía. Use la opción 1.
)
if exist data\bin\openal\soft_oal.dll (
	echo OpenAL Soft está en data\bin\openal.
) else (
	echo Falta data\bin\openal\soft_oal.dll: sin sonido 3D con OpenAL.
)
tasklist /fi "imagename eq nvda.exe" 2>nul | find /i "nvda.exe" >nul && echo NVDA está en ejecución. || echo NVDA no está en ejecución.
tasklist /fi "imagename eq jfw.exe" 2>nul | find /i "jfw.exe" >nul && echo JAWS está en ejecución. || echo JAWS no está en ejecución.
exit /b 0

:CONGELAR
echo.
echo === Guardando las versiones exactas instaladas ===
call :COMPROBAR_VENV || exit /b 1
"%PY%" -m pip freeze > requirements-lock.txt
echo Versiones guardadas en requirements-lock.txt.
exit /b 0

:COMPROBAR_VENV
if exist "%PY%" exit /b 0
echo El entorno virtual no existe. Ejecute primero la opción 1, crear.
exit /b 1

:FIN
endlocal
exit /b 0
