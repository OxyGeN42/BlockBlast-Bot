@echo off
title Block Blast! Bot - iOS Rehber Modu
echo.
echo  ==========================================
echo   Block Blast! Bot - Baslatiliyor...
echo   iOS Rehber Modu
echo  ==========================================
echo.

echo [1/2] Bagimliliklar kontrol ediliyor...
python -m pip install -r requirements.txt --quiet

echo.
echo [2/2] Bot baslatiliyor...
echo.
echo  iOS Kullanim Talimatlari:
echo  -------------------------------------------------------
echo  1. Telefonunuzda Block Blast'i acin
echo  2. LetsView uygulamasini acin ve PC'ye yansitma yapin
echo  3. Bot penceresi acildiginda "Otomatik Bul" butonuna basin
echo  4. "Basla" butonuna basin
echo  5. Bot size hangi bloku nereye koyacaginizi gosterir
echo  6. Siz telefonunuza dokunarak blogu yerlestirir siniz
echo  -------------------------------------------------------
echo.
python ui.py
pause
