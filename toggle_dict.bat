@echo off
rem ============================================================
rem  Vkl/vykl otdelnyh slovarei rusifikatora (GlyphCore).
rem  Loader podhvatyvaet tolko fayly dict_*.csv, poetomu
rem  pereimenovanie v off_dict_*.csv otklyuchaet slovar.
rem
rem  Primery:
rem    toggle_dict items_names   - nazvaniya predmetov EN/RU
rem    toggle_dict skins         - nazvaniya oblikov
rem    toggle_dict maps          - nazvaniya lokaciy
rem    toggle_dict colors        - nazvaniya krasok
rem    toggle_dict minis         - nazvaniya miniatur
rem    toggle_dict               - pokazat status vseh slovarei
rem
rem  Imena personazhei/mest v tekste: translate_proper_nouns
rem  v config.ini (sloi pn_*.csv), etot skript ih ne trogaet.
rem ============================================================
setlocal
cd /d "%~dp0"
if "%~1"=="" goto :status

set "on=dict_%~1.csv"
set "off=off_dict_%~1.csv"
if exist "%on%" (
    ren "%on%" "%off%"
    echo [OFF] %~1 - perevod vyklyuchen, v igre budet angliyskiy
    goto :done
)
if exist "%off%" (
    ren "%off%" "%on%"
    echo [ON]  %~1 - perevod vklyuchen
    goto :done
)
echo Ne naydeno: %on% / %off%
echo Zapustite bez argumentov dlya spiska slovarei.
goto :done

:status
echo === Slovari rusifikatora ===
for %%f in (dict_*.csv) do echo   [ON]  %%~nf
for %%f in (off_dict_*.csv) do echo   [OFF] %%~nf
echo.
echo Perekluchenie: toggle_dict ^<imya bez "dict_" i ".csv"^>

:done
endlocal
