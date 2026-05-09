import os
import logging
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, \
    QHBoxLayout, QGridLayout, QSpinBox, QDialog, QMessageBox, QInputDialog, QStackedWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
import re
from database import init_database, verify_login, get_all_banknote_balances, \
    update_banknote_balance, add_transaction, get_banknote_balance, \
    get_all_overflow_balances, update_overflow_balance

# Get the directory path where the program file is located
current_directory = os.path.dirname(os.path.abspath(__file__))
log_directory = os.path.join(current_directory, "logs")

# Create the logs directory if it doesn't exist
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Create loggers for withdrawals, deposits, admin activities and transactions
withdraw_logger = logging.getLogger("withdraws")
deposit_logger = logging.getLogger("deposits")
admin_logger = logging.getLogger("admin")
transaction_logger = logging.getLogger("transactions")

# Set up file handlers for logging with UTF-8 encoding
withdraw_handler = logging.FileHandler(os.path.join(log_directory, "atmlog-withdraws.log"), encoding='utf-8')
deposit_handler = logging.FileHandler(os.path.join(log_directory, "atmlog-deposits.log"), encoding='utf-8')
admin_handler = logging.FileHandler(os.path.join(log_directory, "atmlog-admin.log"), encoding='utf-8')
transaction_handler = logging.FileHandler(os.path.join(log_directory, "atmlog-transactions.log"), encoding='utf-8')

# Set the log format with UTF-8 support
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
withdraw_handler.setFormatter(formatter)
deposit_handler.setFormatter(formatter)
admin_handler.setFormatter(formatter)
transaction_handler.setFormatter(formatter)

# Add handlers to loggers
withdraw_logger.addHandler(withdraw_handler)
deposit_logger.addHandler(deposit_handler)
admin_logger.addHandler(admin_handler)
transaction_logger.addHandler(transaction_handler)

# Set propagation to False for loggers to prevent duplication
withdraw_logger.propagate = False
deposit_logger.propagate = False
admin_logger.propagate = False
transaction_logger.propagate = False

STACK_CAPACITIES = {
    10: 50,
    20: 50,
    50: 40,
    100: 30,
    200: 30,
    500: 25,
}

class ATM:
    def __init__(self):
        # Załaduj stany banknotów i DEPOZYTU z bazy danych
        self.balance = get_all_banknote_balances()
        self.overflow = get_all_overflow_balances()
        for note in STACK_CAPACITIES:
            self.balance.setdefault(note, 0)
            self.overflow.setdefault(note, 0)
    
    def withdraw(self, amount):
        if amount < 10:
            return None

        best_solution = None
        nodes_explored = [0]  # Licznik eksplorowanych węzłów
        max_nodes = 2000  # Limit węzłów do eksploracji
        
        notes = sorted(self.balance.keys(), reverse=True)

        def backtrack(remaining, current, balance, depth=0):
            nonlocal best_solution
            
            # Limit eksplorowanych węzłów - zapobiega zawieszeniu
            if nodes_explored[0] > max_nodes:
                return
            nodes_explored[0] += 1
            
            # Limit głębokości - zapobiega nieskończonej rekurencji
            if depth > 20:
                return

            if remaining == 0:
                if best_solution is None or is_better(current, best_solution):
                    best_solution = current.copy()
                return

            if remaining < 0:
                return

            # Pruning: jeśli ta ścieżka już nie może być lepsza, przerwij
            if best_solution is not None and depth > 3:
                current_variance = variance(list(current.values()))
                best_variance = variance(list(best_solution.values()))
                if current_variance >= best_variance:
                    return

            for note in notes:
                if balance[note] > 0 and remaining >= note:
                    balance[note] -= 1
                    current[note] += 1

                    backtrack(remaining - note, current, balance, depth + 1)

                    balance[note] += 1
                    current[note] -= 1

        def is_better(sol1, sol2):
            values1 = list(sol1.values())
            values2 = list(sol2.values())
            return variance(values1) < variance(values2)

        def variance(values):
            if not values:
                return 0
            mean = sum(values) / len(values)
            return sum((v - mean) ** 2 for v in values)

        backtrack(amount, {k: 0 for k in self.balance}, self.balance.copy())

        if best_solution:
            for note, count in best_solution.items():
                self.balance[note] -= count
            return best_solution

        return None

    def deposit(self, note, amount):
        if note not in self.balance:
            return 0, 0

        stack_capacity = STACK_CAPACITIES.get(note, 0)
        current_stack = self.balance[note]
        available_space = max(0, stack_capacity - current_stack)
        deposit_to_stack = min(amount, available_space)
        overflow_amount = amount - deposit_to_stack

        self.balance[note] += deposit_to_stack
        self.overflow[note] += overflow_amount

        if deposit_to_stack > 0:
            deposit_logger.info(f"Wpłacono {deposit_to_stack} x {note} zł do kasety ({self.balance[note]}/{stack_capacity})")
        if overflow_amount > 0:
            deposit_logger.info(f"Nadmiar {overflow_amount} x {note} zł trafił do depozytu ({self.overflow[note]} w depozycie)")

        return deposit_to_stack, overflow_amount

    def withdraw_overflow_deposit(self):
        total_overflow = sum(note * qty for note, qty in self.overflow.items())
        if total_overflow == 0:
            return None

        overflow_snapshot = self.overflow.copy()
        self.overflow = {note: 0 for note in self.overflow}
        return overflow_snapshot

    def admin_modify_balance(self, note, amount):
        if note in self.balance:
            self.balance[note] += amount
            admin_logger.info(f"Zmodyfikowano stan konta: {amount} x {note} zł")
    
    def save_to_database(self):
        """Zapisz obecny stan banknotów i depozytu do bazy danych"""
        for denomination, quantity in self.balance.items():
            update_banknote_balance(denomination, quantity)
        for denomination, quantity in self.overflow.items():
            update_overflow_balance(denomination, quantity)

# Color scheme inspired by ING
ING_BLUE = "#0066cc"
ING_ORANGE = "#ff6600"
LIGHT_BG = "#f5f5f5"
DARK_TEXT = "#333333"

def get_large_button_style():
    return f"""
        QPushButton {{
            background-color: {ING_BLUE};
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 24px;
            font-weight: bold;
            padding: 20px;
        }}
        QPushButton:hover {{
            background-color: #0052a3;
        }}
        QPushButton:pressed {{
            background-color: #003d7a;
        }}
    """

def get_secondary_button_style():
    return f"""
        QPushButton {{
            background-color: {ING_ORANGE};
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 18px;
            font-weight: bold;
            padding: 10px;
        }}
        QPushButton:hover {{
            background-color: #ff5500;
        }}
        QPushButton:pressed {{
            background-color: #ff4400;
        }}
    """

def get_small_button_style():
    return f"""
        QPushButton {{
            background-color: {ING_BLUE};
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 18px;
            font-weight: bold;
            padding: 10px;
        }}
        QPushButton:hover {{
            background-color: #0052a3;
        }}
        QPushButton:pressed {{
            background-color: #003d7a;
        }}
    """

def get_disabled_button_style():
    return f"""
        QPushButton {{
            background-color: #cccccc;
            color: #999999;
            border: none;
            border-radius: 5px;
            font-size: 18px;
            font-weight: bold;
            padding: 10px;
        }}
        QPushButton:disabled {{
            background-color: #cccccc;
            color: #999999;
        }}
    """

class LoginScreen(QWidget):
    def __init__(self, atm, parent=None):
        super().__init__(parent)
        self.atm = atm
        self.parent_window = parent
        self.current_field = 'client_id'  # Śledzenie aktywnego pola

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Title
        title = QLabel("Bankomat")
        title_font = QFont()
        title_font.setPointSize(48)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {ING_BLUE};")
        layout.addWidget(title)

        layout.addSpacing(40)

        # Client ID label
        client_id_label = QLabel("Numer klienta (7 cyfr):")
        client_id_font = QFont()
        client_id_font.setPointSize(18)
        client_id_label.setFont(client_id_font)
        layout.addWidget(client_id_label)

        # Client ID entry
        self.client_id_entry = QLineEdit()
        self.client_id_entry.setFixedHeight(60)
        entry_font = QFont()
        entry_font.setPointSize(20)
        self.client_id_entry.setFont(entry_font)
        self.client_id_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.client_id_entry.setMaxLength(7)
        layout.addWidget(self.client_id_entry)

        layout.addSpacing(20)

        # PIN label
        pin_label = QLabel("PIN:")
        pin_font = QFont()
        pin_font.setPointSize(18)
        pin_label.setFont(pin_font)
        layout.addWidget(pin_label)

        # PIN entry
        self.pin_entry = QLineEdit()
        self.pin_entry.setFixedHeight(60)
        self.pin_entry.setFont(entry_font)
        self.pin_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pin_entry.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.pin_entry)

        layout.addSpacing(30)

        # Number buttons
        numbers_layout = QGridLayout()
        numbers_layout.setSpacing(10)
        button_size = 60

        self.digit_buttons = {}

        for i in range(10):
            button = QPushButton(str(i))
            button.setStyleSheet(get_small_button_style())
            button.setFixedHeight(button_size)
            button.setFixedWidth(button_size)
            button.clicked.connect(self.create_digit_handler(i))
            self.digit_buttons[i] = button
            numbers_layout.addWidget(button, (9 - i) // 3, (9 - i) % 3)

        # Backspace button
        backspace_btn = QPushButton("⌫")
        backspace_btn.setStyleSheet(get_small_button_style())
        backspace_btn.setFixedHeight(button_size)
        backspace_btn.setFixedWidth(button_size)
        backspace_btn.clicked.connect(self.backspace)
        numbers_layout.addWidget(backspace_btn, 3, 2)

        layout.addLayout(numbers_layout)
        layout.addStretch()

        # Login button
        login_btn = QPushButton("Zaloguj")
        login_btn.setStyleSheet(get_secondary_button_style())
        login_btn.setFixedHeight(70)
        login_btn.clicked.connect(self.login)
        layout.addWidget(login_btn)

        self.setLayout(layout)

    def create_digit_handler(self, digit):
        def handler():
            self.add_digit(str(digit))
        return handler

    def add_digit(self, digit):
        # Jeśli client_id nie ma 7 cyfr, dodaj do niego
        if len(self.client_id_entry.text()) < 7:
            current = self.client_id_entry.text()
            if current.isdigit() or current == "":
                self.client_id_entry.setText(current + digit)
                self.current_field = 'client_id'
        # W innym razie dodaj do PIN
        else:
            current = self.pin_entry.text()
            if len(current) < 8:  # Max 8 dla administratora
                self.pin_entry.setText(current + digit)
                self.current_field = 'pin'

    def backspace(self):
        # Usuń z aktualnie edytowanego pola na podstawie self.current_field
        if self.current_field == 'pin':
            current_pin = self.pin_entry.text()
            if current_pin:
                self.pin_entry.setText(current_pin[:-1])
            # Jeśli PIN stał się pusty, przełącz na client_id
            if not self.pin_entry.text():
                self.current_field = 'client_id'
        else:  # client_id
            current_id = self.client_id_entry.text()
            if current_id:
                self.client_id_entry.setText(current_id[:-1])
                self.current_field = 'client_id'
            # Jeśli client_id stał się pusty, zostań na client_id
            if not self.client_id_entry.text():
                self.current_field = 'client_id'

    def login(self):
        client_id = self.client_id_entry.text()
        pin = self.pin_entry.text()

        # Weryfikacja
        if len(client_id) != 7:
            QMessageBox.warning(self, "Błąd", "Numer klienta musi mieć 7 cyfr")
            return

        if len(pin) not in [4, 8]:
            QMessageBox.warning(self, "Błąd", "PIN nieprawidłowy")
            return

        # Weryfikuj logowanie
        user = verify_login(client_id, pin)
        if user:
            if self.parent_window:
                self.parent_window.login_user(user)
            self.client_id_entry.clear()
            self.pin_entry.clear()
        else:
            QMessageBox.warning(self, "Błąd", "Nieprawidłowy numer klienta lub PIN")
            self.pin_entry.clear()


class AdminScreen(QWidget):
    def __init__(self, atm, parent=None):
        super().__init__(parent)
        self.atm = atm
        self.parent_window = parent
        self.spin_boxes = {}
        self.planned_changes = {}  # Śledzenie zaplanowanych zmian

        self.layout = QVBoxLayout()

        # Title
        title = QLabel("Panel Administratora")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(title)

        # Result label for feedback
        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result_font = QFont()
        result_font.setPointSize(16)
        self.result_label.setFont(result_font)
        self.layout.addWidget(self.result_label)

        # Admin content
        self.stacks_layout = QGridLayout()
        self.count_labels = {}  # Przechowuj odwołania do etykiet liczby
        
        for i, (note, count) in enumerate(sorted(self.atm.balance.items())):
            label = QLabel(f"{note} zł:")
            label_font = QFont()
            label_font.setPointSize(16)
            label.setFont(label_font)
            
            count_label = QLabel(str(count))
            count_label_font = QFont()
            count_label_font.setPointSize(14)
            count_label.setFont(count_label_font)
            self.count_labels[note] = count_label
            
            add_button = QPushButton("+")
            add_button.setStyleSheet(get_small_button_style())
            add_button.setFixedHeight(50)
            add_button.setFixedWidth(50)
            add_button.clicked.connect(self.create_add_handler(note))
            
            subtract_button = QPushButton("-")
            subtract_button.setStyleSheet(get_small_button_style())
            subtract_button.setFixedHeight(50)
            subtract_button.setFixedWidth(50)
            subtract_button.clicked.connect(self.create_subtract_handler(note))
            
            spin_box = QSpinBox()
            spin_box.setValue(1)
            spin_box.setMaximum(100)  # Zwiększony max dla admina
            spin_box.setFixedHeight(40)
            spin_box_font = QFont()
            spin_box_font.setPointSize(14)
            spin_box.setFont(spin_box_font)

            self.stacks_layout.addWidget(label, i, 0)
            self.stacks_layout.addWidget(count_label, i, 1)
            self.stacks_layout.addWidget(add_button, i, 2)
            self.stacks_layout.addWidget(subtract_button, i, 3)
            self.stacks_layout.addWidget(spin_box, i, 4)

            self.spin_boxes[note] = spin_box
            self.planned_changes[note] = 0  # Inicjalizuj planned_changes

        self.layout.addLayout(self.stacks_layout)

        # Overflow deposit summary
        self.overflow_summary_label = QLabel("")
        overflow_font = QFont()
        overflow_font.setPointSize(14)
        self.overflow_summary_label.setFont(overflow_font)
        self.overflow_summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overflow_summary_label.setStyleSheet("color: #333333;")
        self.layout.addWidget(self.overflow_summary_label)

        self.overflow_deposit_button = QPushButton("Opróżnij depozyt")
        self.overflow_deposit_button.setStyleSheet(get_secondary_button_style())
        self.overflow_deposit_button.setFixedHeight(70)
        self.overflow_deposit_button.setFixedWidth(220)
        self.overflow_deposit_button.clicked.connect(self.withdraw_overflow_deposit)
        self.overflow_deposit_button.setVisible(False)
        self.layout.addWidget(self.overflow_deposit_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.layout.addStretch()

        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        save_btn = QPushButton("Zatwierdź")
        save_btn.setStyleSheet(get_secondary_button_style())
        save_btn.setFixedHeight(70)
        save_btn.setFixedWidth(200)
        save_btn.clicked.connect(self.save_changes)
        buttons_layout.addWidget(save_btn)

        logout_btn = QPushButton("Wyloguj")
        logout_btn.setStyleSheet(get_secondary_button_style())
        logout_btn.setFixedHeight(70)
        logout_btn.setFixedWidth(200)
        logout_btn.clicked.connect(self.logout)
        buttons_layout.addWidget(logout_btn)

        self.layout.addLayout(buttons_layout)

        self.setLayout(self.layout)

    def create_add_handler(self, note):
        """Utwórz handler dla przycisku dodawania"""
        def handler():
            self.add_banknotes(note)
        return handler

    def create_subtract_handler(self, note):
        """Utwórz handler dla przycisku odejmowania"""
        def handler():
            self.subtract_banknotes(note)
        return handler

    def add_banknotes(self, note):
        spin_box = self.spin_boxes[note]
        amount = spin_box.value()
        if amount > 0:
            self.planned_changes[note] += amount
            self.update_display()

    def subtract_banknotes(self, note):
        spin_box = self.spin_boxes[note]
        amount = spin_box.value()
        if amount > 0:
            self.planned_changes[note] -= amount
            self.update_display()

    def update_display(self):
        """Zaktualizuj wyświetlane liczby bez modyfikacji self.atm.balance"""
        for note, count_label in self.count_labels.items():
            new_count = self.atm.balance[note] + self.planned_changes[note]
            # Pokaż liczbę w czerwonym kolorze jeśli byłaby ujemna
            if new_count < 0:
                count_label.setStyleSheet("color: #ff0000;")
            else:
                count_label.setStyleSheet("color: #000000;")
            count_label.setText(str(max(0, new_count)))  # Pokaż 0 jeśli ujemne
        self.update_overflow_display()

    def update_overflow_display(self):
        """Zaktualizuj opis stanu depozytu"""
        overflow_lines = [f"{note} zł: {self.atm.overflow[note]}" for note in sorted(self.atm.overflow.keys())]
        self.overflow_summary_label.setText("Depozyt: " + ", ".join(overflow_lines))

    def refresh_admin_controls(self):
        if self.parent_window and self.parent_window.current_user:
            is_superadmin = self.parent_window.current_user['client_id'] == '0000001'
            self.overflow_deposit_button.setVisible(is_superadmin)
        else:
            self.overflow_deposit_button.setVisible(False)

    def withdraw_overflow_deposit(self):
        if not self.parent_window or not self.parent_window.current_user:
            return
        if self.parent_window.current_user['client_id'] != '0000001':
            QMessageBox.warning(self, "Brak uprawnień", "Tylko superadmin może opróżnić depozyt.")
            return

        overflow_snapshot = self.atm.withdraw_overflow_deposit()
        if not overflow_snapshot:
            QMessageBox.information(self, "Depozyt", "Brak środków w depozycie.")
            return

        total_overflow = sum(note * qty for note, qty in overflow_snapshot.items())
        details = ", ".join([f"{qty}x {note}zł" for note, qty in overflow_snapshot.items() if qty > 0])
        add_transaction(
            self.parent_window.current_user['client_id'],
            "overflow_deposit_withdrawal",
            total_overflow,
            details
        )
        admin_logger.info(f"Superadmin {self.parent_window.current_user['client_id']} opróżnił depozyt: {details}")
        transaction_logger.info(f"Superadmin {self.parent_window.current_user['client_id']} - OPRÓŻNIENIE DEPOZYTU: {details}")
        self.atm.save_to_database()
        self.update_display()
        QMessageBox.information(self, "Depozyt", "Depozyt został opróżniony.")

    def save_changes(self):
        """Zastosuj wszystkie zaplanowane zmiany i zarejestruj transakcje"""
        # Sprawdzenie czy wszystkie zmiany byłyby prawidłowe
        for note, change in self.planned_changes.items():
            if self.atm.balance[note] + change < 0:
                QMessageBox.warning(self, "Błąd", f"Niewystarczająca ilość banknotów {note} zł")
                return
        
        # Zastosuj zmiany i zarejestruj transakcje
        admin_id = self.parent_window.current_user['client_id'] if self.parent_window and self.parent_window.current_user else None
        admin_name = self.parent_window.current_user['name'] if self.parent_window and self.parent_window.current_user else "Nieznany"
        
        # Zbierz informacje o zmianach dla logu
        deposits_changes = []
        withdrawals_changes = []
        
        for note, change in self.planned_changes.items():
            if change != 0:
                self.atm.balance[note] += change
                
                # Rejestruj transakcję
                if change > 0:
                    add_transaction(admin_id, "admin_deposit", change * note, f"{change}x {note}zł")
                    deposits_changes.append(f"{change}x {note}zł")
                else:
                    add_transaction(admin_id, "admin_withdraw", abs(change * note), f"{abs(change)}x {note}zł")
                    withdrawals_changes.append(f"{abs(change)}x {note}zł")
        
        # Zapisz do bazy danych
        self.atm.save_to_database()
        
        # Zaloguj szczegółowe informacje o zmianach
        changes_summary = []
        if deposits_changes:
            changes_summary.append(f"Dodał: {', '.join(deposits_changes)}")
        if withdrawals_changes:
            changes_summary.append(f"Usunął: {', '.join(withdrawals_changes)}")
        
        changes_detail = " | ".join(changes_summary) if changes_summary else "Brak zmian"
        admin_logger.info(f"Administrator {admin_id} ({admin_name}) zatwierdził zmiany: {changes_detail}")
        
        # Resetuj zaplanowane zmiany
        self.planned_changes = {note: 0 for note in self.planned_changes}
        self.update_display()
        
        self.result_label.setText("✓ Zmiany zatwierdzone i zapisane")
        self.result_label.setStyleSheet("color: #00aa00; font-weight: bold;")
        QTimer.singleShot(3000, lambda: self.result_label.setText(""))

    def logout(self):
        """Wyloguj się z panelu administratora"""
        # Resetuj zaplanowane zmiany, jeśli nie zostały zatwierdzone
        self.planned_changes = {note: 0 for note in self.planned_changes}
        self.update_display()
        
        if self.parent_window:
            admin_logger.info("Administrator się wylogował")
            self.parent_window.logout_user()


class MainScreen(QWidget):
    def __init__(self, atm, parent=None):
        super().__init__(parent)
        self.atm = atm
        self.parent_window = parent
        self.admin_click_count = 0
        self.admin_timer = None
        self.current_user = None

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(30)

        # User info bar at top
        user_layout = QHBoxLayout()
        self.user_label = QLabel("")
        user_font = QFont()
        user_font.setPointSize(14)
        self.user_label.setFont(user_font)
        self.user_label.setStyleSheet(f"color: {ING_BLUE};")
        user_layout.addWidget(self.user_label)
        user_layout.addStretch()

        logout_btn = QPushButton("Wyloguj")
        logout_btn.setStyleSheet(get_secondary_button_style())
        logout_btn.setFixedHeight(50)
        logout_btn.setFixedWidth(120)
        logout_btn.clicked.connect(self.logout)
        user_layout.addWidget(logout_btn)
        layout.addLayout(user_layout)

        # Title - clickable for admin access
        self.title = QLabel("Bankomat")
        self.title.setCursor(Qt.CursorShape.PointingHandCursor)
        self.title.mousePressEvent = self.on_title_click
        title_font = QFont()
        title_font.setPointSize(48)
        title_font.setBold(True)
        self.title.setFont(title_font)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(f"color: {ING_BLUE};")
        layout.addWidget(self.title)

        layout.addStretch()

        # Withdrawal button
        withdraw_btn = QPushButton("Wypłata")
        withdraw_btn.setStyleSheet(get_large_button_style())
        withdraw_btn.setFixedHeight(120)
        withdraw_btn.setFixedWidth(400)
        withdraw_btn.clicked.connect(self.go_to_withdraw)
        layout.addWidget(withdraw_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Deposit button
        deposit_btn = QPushButton("Wpłata")
        deposit_btn.setStyleSheet(get_large_button_style())
        deposit_btn.setFixedHeight(120)
        deposit_btn.setFixedWidth(400)
        deposit_btn.clicked.connect(self.go_to_deposit)
        layout.addWidget(deposit_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

        self.setLayout(layout)

    def set_user(self, user):
        """Ustaw zalogowanego użytkownika"""
        self.current_user = user
        self.user_label.setText(f"Zalogowany: {user['name']} ({user['client_id']})")

    def logout(self):
        """Wyloguj użytkownika"""
        if self.parent_window:
            self.parent_window.logout_user()

    def go_to_withdraw(self):
        if self.parent_window:
            self.parent_window.switch_screen(2)

    def go_to_deposit(self):
        if self.parent_window:
            self.parent_window.switch_screen(3)

    def on_title_click(self, event):
        # 5x klik dostępny tylko dla admina (nie superadmina)
        if self.current_user and self.current_user['is_admin'] and self.current_user['client_id'] != '0000001':
            self.admin_click_count += 1
            
            if self.admin_timer is None:
                self.admin_timer = QTimer()
                self.admin_timer.setSingleShot(True)
                self.admin_timer.timeout.connect(self.reset_click_count)
            
            self.admin_timer.stop()
            self.admin_timer.start(2000)  # 2 second window

            if self.admin_click_count >= 5:
                self.admin_click_count = 0
                self.admin_timer.stop()
                if self.parent_window:
                    self.parent_window.switch_screen(4)

    def reset_click_count(self):
        self.admin_click_count = 0


class WithdrawScreen(QWidget):
    def __init__(self, atm, parent=None):
        super().__init__(parent)
        self.atm = atm
        self.parent_window = parent

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Wypłata")
        title_font = QFont()
        title_font.setPointSize(36)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {ING_BLUE};")
        layout.addWidget(title)

        # Amount label
        amount_label = QLabel("Wprowadź kwotę:")
        amount_font = QFont()
        amount_font.setPointSize(20)
        amount_label.setFont(amount_font)
        layout.addWidget(amount_label)

        # Amount entry
        self.amount_entry = QLineEdit()
        self.amount_entry.setFixedHeight(60)
        entry_font = QFont()
        entry_font.setPointSize(24)
        self.amount_entry.setFont(entry_font)
        self.amount_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.amount_entry.textChanged.connect(self.validate_amount_entry)
        layout.addWidget(self.amount_entry)

        # Number buttons
        numbers_layout = QGridLayout()
        numbers_layout.setSpacing(10)
        button_size = 80 

        self.digit_buttons = {}  # Store references to digit buttons

        for i in range(10):
            button = QPushButton(str(i))
            button.setStyleSheet(get_small_button_style())
            button.setFixedHeight(button_size)
            button.setFixedWidth(button_size)
            button.clicked.connect(self.create_digit_handler(i))
            self.digit_buttons[i] = button
            numbers_layout.addWidget(button, (9 - i) // 3, (9 - i) % 3)

        # Disable zero button initially
        self.digit_buttons[0].setEnabled(False)
        self.digit_buttons[0].setStyleSheet(get_disabled_button_style())

        # Backspace button
        backspace_btn = QPushButton("⌫")
        backspace_btn.setStyleSheet(get_small_button_style())
        backspace_btn.setFixedHeight(button_size)
        backspace_btn.setFixedWidth(button_size)
        backspace_btn.clicked.connect(self.remove_last_digit)
        numbers_layout.addWidget(backspace_btn, 3, 2)

        layout.addLayout(numbers_layout)

        # Result label
        self.result_label = QLabel("")
        result_font = QFont()
        result_font.setPointSize(16)
        self.result_label.setFont(result_font)
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet(f"color: {DARK_TEXT};")
        layout.addWidget(self.result_label)

        layout.addStretch()

        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        withdraw_btn = QPushButton("Wypłać")
        withdraw_btn.setStyleSheet(get_secondary_button_style())
        withdraw_btn.setFixedHeight(70)
        withdraw_btn.setFixedWidth(200)
        withdraw_btn.clicked.connect(self.withdraw)
        withdraw_btn.setEnabled(False)
        self.withdraw_btn = withdraw_btn
        buttons_layout.addWidget(withdraw_btn)

        back_btn = QPushButton("Powrót")
        back_btn.setStyleSheet(get_secondary_button_style())
        back_btn.setFixedHeight(70)
        back_btn.setFixedWidth(200)
        back_btn.clicked.connect(self.go_back)
        buttons_layout.addWidget(back_btn)

        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def create_digit_handler(self, digit):
        def handler():
            self.add_digit(str(digit))
        return handler

    def validate_amount_entry(self, text):
        if not text.isdigit() and text != "":
            self.amount_entry.setText(re.sub(r'\D', '', text))
        else:
            if text == "":
                self.withdraw_btn.setEnabled(False)
                # Disable zero button when empty
                self.digit_buttons[0].setEnabled(False)
                self.digit_buttons[0].setStyleSheet(get_disabled_button_style())
            else:
                amount = int(text)
                self.withdraw_btn.setEnabled(amount >= 10)
                # Enable zero button when there's any digit
                self.digit_buttons[0].setEnabled(True)
                self.digit_buttons[0].setStyleSheet(get_small_button_style())

    def add_digit(self, digit):
        current = self.amount_entry.text()
        self.amount_entry.setText(current + digit)

    def remove_last_digit(self):
        current = self.amount_entry.text()
        self.amount_entry.setText(current[:-1])

    def withdraw(self):
        amount = int(self.amount_entry.text())

        # Walidacja: tylko wielokrotności 10
        if amount % 10 != 0:
            result_text = "Nie można wypłacić żądanej kwoty. Wypłata możliwa tylko w nominałach dostępnych w bankomacie (wielokrotności 10 zł)"
            self.result_label.setStyleSheet("color: #ff0000;")
            self.result_label.setText(result_text)
            self.amount_entry.clear()

            transaction_logger.warning(f"Użytkownik {self.parent_window.current_user['client_id']} ({self.parent_window.current_user['name']}) - NIEUDANA WYPŁATA: {amount} zł - Niepoprawna kwota (nie jest wielokrotnością 10)")
            withdraw_logger.warning(f"Nie można wypłacić {amount} zł dla użytkownika {self.parent_window.current_user['client_id']} ({self.parent_window.current_user['name']}) - Niepoprawna kwota (nie jest wielokrotnością 10)")
            return

        withdrawn_notes = self.atm.withdraw(amount)

        if withdrawn_notes is not None:
            # Sukces
            if self.parent_window and self.parent_window.current_user:
                user_id = self.parent_window.current_user['client_id']
                user_name = self.parent_window.current_user['name']
                details = ", ".join([f"{count}x {note}zł" for note, count in withdrawn_notes.items() if count > 0])

                add_transaction(
                 user_id,
                 "WITHDRAWAL",
                 amount,
                 details
                )

                transaction_logger.info(f"Użytkownik {user_id} ({user_name}) - WYPŁATA: {amount} zł | {details}")
                withdraw_logger.info(f"Wypłacono {amount} zł dla użytkownika {user_id} ({user_name}) - {details}")

            result_text = "Wypłata udana!\nWypłacone banknoty:\n"
            for note, count in withdrawn_notes.items():
                if count > 0:
                    result_text += f"{count}x {note} zł "

            self.result_label.setStyleSheet("color: #00aa00;")

            # Zapisz stan ATM
            self.atm.save_to_database()

        else:
            # Brak możliwości wypłaty (banknoty / środki)
            result_text = "Nie można wypłacić żądanej kwoty - brak odpowiednich banknotów lub niewystarczające środki w bankomacie."
            self.result_label.setStyleSheet("color: #ff0000;")

            transaction_logger.warning(f"Użytkownik {self.parent_window.current_user['client_id']} ({self.parent_window.current_user['name']}) - NIEUDANA WYPŁATA: {amount} zł - Brak banknotów lub środków")
            withdraw_logger.warning(f"Nie można wypłacić {amount} zł dla użytkownika {self.parent_window.current_user['client_id']} ({self.parent_window.current_user['name']}) - brak odpowiednich banknotów lub środków")

        self.result_label.setText(result_text)
        self.amount_entry.clear()
    
    def go_back(self):
        self.amount_entry.clear()
        self.result_label.setText("")
        if self.parent_window:
            self.parent_window.switch_screen(0)


class DepositScreen(QWidget):
    def __init__(self, atm, parent=None):
        super().__init__(parent)
        self.atm = atm
        self.parent_window = parent

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Wpłata")
        title_font = QFont()
        title_font.setPointSize(36)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {ING_BLUE};")
        layout.addWidget(title)

        # Instructions
        instructions = QLabel("Wybierz banknot i ilość:")
        instr_font = QFont()
        instr_font.setPointSize(18)
        instructions.setFont(instr_font)
        layout.addWidget(instructions)

        # Deposit options
        deposit_layout = QGridLayout()
        deposit_layout.setSpacing(15)

        self.spin_boxes = {}
        
        for i, note in enumerate(sorted(self.atm.balance.keys())):
            label = QLabel(f"{note} zł:")
            label_font = QFont()
            label_font.setPointSize(18)
            label.setFont(label_font)

            spin_box = QSpinBox()
            spin_box.setValue(1)
            spin_box.setMinimum(0)
            spin_box.setFixedHeight(50)
            spin_box_font = QFont()
            spin_box_font.setPointSize(16)
            spin_box.setFont(spin_box_font)

            deposit_layout.addWidget(label, i, 0)
            deposit_layout.addWidget(spin_box, i, 1)

            self.spin_boxes[note] = spin_box

        layout.addLayout(deposit_layout)
        layout.addStretch()

        # Result label
        self.result_label = QLabel("")
        result_font = QFont()
        result_font.setPointSize(16)
        self.result_label.setFont(result_font)
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet(f"color: {DARK_TEXT};")
        layout.addWidget(self.result_label)

        layout.addStretch()

        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        confirm_btn = QPushButton("Potwierdź")
        confirm_btn.setStyleSheet(get_secondary_button_style())
        confirm_btn.setFixedHeight(70)
        confirm_btn.setFixedWidth(200)
        confirm_btn.clicked.connect(self.confirm_deposit)
        buttons_layout.addWidget(confirm_btn)

        back_btn = QPushButton("Powrót")
        back_btn.setStyleSheet(get_secondary_button_style())
        back_btn.setFixedHeight(70)
        back_btn.setFixedWidth(200)
        back_btn.clicked.connect(self.go_back)
        buttons_layout.addWidget(back_btn)

        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def confirm_deposit(self):
        total = sum(note * spin_box.value() for note, spin_box in self.spin_boxes.items())
        if total > 0:
            overflow_deposit_messages = []
            deposit_details = []
            overflow_total = 0
            for note, spin_box in self.spin_boxes.items():
                amount = spin_box.value()
                if amount > 0:
                    stack_added, overflow_added = self.atm.deposit(note, amount)
                    deposit_details.append(f"{amount}x {note}zł")
                    if overflow_added > 0:
                        overflow_deposit_messages.append(f"{overflow_added}x {note}zł trafiło do depozytu")
                        overflow_total += overflow_added * note
            
            if self.parent_window and self.parent_window.current_user:
                user_id = self.parent_window.current_user['client_id']
                user_name = self.parent_window.current_user['name']
                details = ", ".join(deposit_details)
                add_transaction(
                    user_id,
                    "DEPOSIT",
                    total,
                    details
                )
                transaction_logger.info(f"Użytkownik {user_id} ({user_name}) - WPŁATA: {total} zł | {details}")
                if overflow_deposit_messages:
                    overflow_details = ", ".join(overflow_deposit_messages)
                    deposit_logger.info(f"Nadmiar przy wpłacie skierowany do depozytu: {overflow_details}")
                    transaction_logger.info(f"WPŁATA DEPOZYT: {user_id} ({user_name}) - {overflow_details}")
                    add_transaction(
                        user_id,
                        "deposit_overflow",
                        overflow_total,
                        overflow_details
                    )
            
            self.atm.save_to_database()
            
            result_text = f"Wpłata udana!\nWpłacono {total} zł"
            self.result_label.setText(result_text)
            self.result_label.setStyleSheet(f"color: #00aa00;")
        else:
            result_text = "Nie wybrano żadnych banknotów"
            self.result_label.setText(result_text)
            self.result_label.setStyleSheet(f"color: #ff0000;")

    def go_back(self):
        for spin_box in self.spin_boxes.values():
            spin_box.setValue(0)
        self.result_label.setText("")
        self.result_label.setStyleSheet(f"color: {DARK_TEXT};")
        if self.parent_window:
            self.parent_window.switch_screen(0)

class ATMGUI(QWidget):
    def __init__(self, atm):
        super().__init__()
        self.atm = atm
        self.current_user = None

        self.setStyleSheet(f"background-color: {LIGHT_BG};")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Stacked widget for screens
        self.stacked_widget = QStackedWidget()

        # Create screens with parent reference
        self.login_screen = LoginScreen(atm, self)
        self.main_screen = MainScreen(atm, self)
        self.withdraw_screen = WithdrawScreen(atm, self)
        self.deposit_screen = DepositScreen(atm, self)
        self.admin_screen = AdminScreen(atm, self)

        # Add screens to stacked widget
        self.stacked_widget.addWidget(self.login_screen)     # 0
        self.stacked_widget.addWidget(self.main_screen)      # 1
        self.stacked_widget.addWidget(self.withdraw_screen)  # 2
        self.stacked_widget.addWidget(self.deposit_screen)   # 3
        self.stacked_widget.addWidget(self.admin_screen)     # 4

        layout.addWidget(self.stacked_widget)
        self.setLayout(layout)
        
        # Pokaż ekran logowania na start
        self.stacked_widget.setCurrentIndex(0)

    def login_user(self, user):
        """Zaloguj użytkownika"""
        self.current_user = user
        self.main_screen.set_user(user)
        
        # Jeśli superadmin (0000001), idź do panelu admina, inaczej do ekranu głównego
        if user['is_admin'] and user['client_id'] == '0000001':
            self.switch_screen(4)
        else:
            self.switch_screen(1)

    def logout_user(self):
        """Wyloguj użytkownika"""
        self.current_user = None
        self.main_screen.current_user = None
        self.stacked_widget.setCurrentIndex(0)

    def switch_screen(self, screen_index):
        self.stacked_widget.setCurrentIndex(screen_index)
        # Reset screens when switching
        if screen_index == 2:
            self.withdraw_screen.amount_entry.clear()
            self.withdraw_screen.result_label.setText("")
            self.withdraw_screen.digit_buttons[0].setEnabled(False)
            self.withdraw_screen.digit_buttons[0].setStyleSheet(get_disabled_button_style())
        elif screen_index == 3:
            for spin_box in self.deposit_screen.spin_boxes.values():
                spin_box.setValue(0)
            self.deposit_screen.result_label.setText("")
            self.deposit_screen.result_label.setStyleSheet(f"color: {DARK_TEXT};")
        elif screen_index == 4:
            self.admin_screen.planned_changes = {note: 0 for note in self.admin_screen.planned_changes}
            self.admin_screen.refresh_admin_controls()
            self.admin_screen.update_display()
            self.admin_screen.result_label.setText("")

    # === FULLSCREEN ===
    def keyPressEvent(self, event):
        """Obsługa klawisza Escape do opuszczenia fullscreen (do testowania)"""
        if event.key() == Qt.Key_Escape:
            self.showNormal()
        super().keyPressEvent(event)
    # === FULLSCREEN ===


def main():
    app = QApplication([])
    
    # Zainicjalizuj bazę danych
    init_database()
    
    atm = ATM()
    window = ATMGUI(atm)
    
    # === FULLSCREEN ===
    # Ustawienie okna na pełny ekran bez ramek
    window.setWindowTitle("Symulacja bankomatu")
    window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    window.showFullScreen()
    # === FULLSCREEN ===
    
    app.exec()


if __name__ == "__main__":
    main()
