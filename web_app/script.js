let tg = window.Telegram.WebApp;

tg.expand();
tg.MainButton.textColor = '#FFFFFF';
tg.MainButton.color = '#2cab37';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Apply theme params if needed (usually handled by CSS variables, but we can double check)
    // Actually CSS var() handles it if we used TG vars, but we hardcoded for simplicity.
    // Let's use TG params for better integration if available
    if (tg.themeParams.bg_color) {
        document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color);
        document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color);
        document.documentElement.style.setProperty('--tg-theme-hint-color', tg.themeParams.hint_color);
        document.documentElement.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color);
        document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.themeParams.button_text_color);
        document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams.secondary_bg_color);
    }
});

let taskInput = document.getElementById("taskInput");
let categorySelect = document.getElementById("categorySelect");
let dateInput = document.getElementById("dateInput");
let timeInput = document.getElementById("timeInput");

// Show button if text exists
taskInput.addEventListener('input', () => {
    if (taskInput.value.trim().length > 0) {
        tg.MainButton.setText("Создать задачу");
        tg.MainButton.show();
    } else {
        tg.MainButton.hide();
    }
});

// Handle Button Click
Telegram.WebApp.onEvent('mainButtonClicked', function () {
    let data = {
        action: "create_task",
        text: taskInput.value.trim(),
        category: categorySelect.value,
        date: dateInput.value,
        time: timeInput.value
    };

    tg.sendData(JSON.stringify(data));
});
