Użyte technologie

VS Code 1.87.0
Wersja Pythona 3.11.5 'base' anaconda3
Pakiety:
    PySide6 (pip install PySide6) (6.6.2)
    shiboken6==6.6.2 (from PySide6) (6.6.2)
    PySide6-Essentials==6.6.2 (from PySide6) (6.6.2)
    PySide6-Addons==6.6.2 (from PySide6) (6.6.2)   

Aplikacje należy uruchomić w środowisku VS Code 

Plik programu można wypakować do dowolnego folderu

## Dane do logowania testowego

### Klienci normalni (PIN: 4 cyfry)
- Numer: `1234567`, PIN: `1234` - Jan Kowalski
- Numer: `2345678`, PIN: `5678` - Maria Nowak

### Super Administrator (PIN: 8 cyfr)
- Numer: `0000001`, PIN: `12345678`

### Administrator (PIN: 8 cyfr)
- Numer: `1014872`, PIN: `10221142`

## Architektura bazy danych

### Tabela `clients`
- `client_id` (TEXT): Numer klienta (7 cyfr)
- `pin` (TEXT): Hasło/PIN (4 lub 8 cyfr)
- `name` (TEXT): Imię i nazwisko
- `balance` (REAL): Saldo konta
- `is_admin` (INTEGER): Flaga administratora
- `created_at` (TIMESTAMP): Data utworzenia

### Tabela `banknote_balance`
- `denomination` (INTEGER): Nominał banknotu (10, 20, 50, 100, 200, 500)
- `quantity` (INTEGER): Ilość banknotów

### Tabela `transactions`
- `transaction_id` (INTEGER): ID transakcji
- `client_id` (TEXT): Numer klienta
- `transaction_type` (TEXT): Typ (WITHDRAWAL/DEPOSIT)
- `amount` (REAL): Kwota
- `timestamp` (TIMESTAMP): Data i czas
- `details` (TEXT): Szczegóły (jakie banknoty)

## Funkcje aplikacji

1. **Logowanie**: Wpisz 7-cyfrowy numer klienta i PIN (4 lub 8 cyfr)
2. **Wypłata**: Wprowadź kwotę (min. 10 zł), system automatycznie wybierze banknoty
3. **Wpłata**: Wybierz banknoty i ilość
4. **Panel Administratora**: Zarządzaj stanem banknotów
5. **Persistent storage**: Stany banknotów i transakcje są zapisywane w bazie

## Działanie ekranów

- **Ekran logowania**: Klawiatura numeryczna dla wygody
- **Ekran główny**: Opcje Wypłaty, Wpłaty, wylogowanie
- **Ekran wypłaty**: Klawiatura numeryczna, przycisk 0 wyszarowany do czasu wpisania cyfry
- **Ekran wpłaty**: Spinboxy do wyboru ilości banknotów
- **Panel administratora**: Dostęp po zalogowaniu się jako admin (0000001)

## Algorytm wypłat

System używa sprytnego algorytmu opartego na backtrackingu z pruningiem:
- **Sprawiedliwa dystrybucja**: Rozkład banknotów jest równomierny (minimalizuje wariancję)
- **Szybkość**: Ograniczony backtracking (max 2000 węzłów) zapewnia <50ms dla większości kwot
- **Pruning**: Odcinanie gałęzi które nie mogą być lepsze niż bieżące rozwiązanie

Przykłady:
- 1180 zł → 1x 10zł, 1x 20zł, 1x 50zł, 2x 100zł, 2x 200zł, 1x 500zł (sprawiedliwe)
- 2340 zł → 3x 10zł, 3x 20zł, 3x 50zł, 2x 100zł, 2x 200zł, 3x 500zł (równomierne)

## Panel Administratora

- **Przycisk "Zatwierdź"**: Zapisuje bieżący stan banknotów do bazy danych
- **Przycisk "Wyloguj"**: Wylogowuje się z panelu i powraca do ekranu logowania
- Komunikaty o sukcesie wyświetlane na ekranie (zielony tekst)

## Uruchamianie aplikacji

### Windows
1. Otwórz katalog projektu w Eksploratorze lub w wierszu poleceń.
2. Uruchom plik `run_windows.bat` dwukrotnie klikając go lub w konsoli.

### Linux / Kali
1. Otwórz terminal w katalogu projektu.
2. Nadaj prawa do uruchamiania:
   ```bash
   chmod +x run_linux.sh
   ```
3. Uruchom aplikację:
   ```bash
   ./run_linux.sh
   ```

### Wymagania
- Python 3
- PySide6
- Baza danych `atm.db` w katalogu projektu (powinna być utworzona automatycznie przez aplikację)
