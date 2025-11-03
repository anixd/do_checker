(function() {
    const STORAGE_KEY = 'theme';
    const TOGGLE_CHECKBOX_ID = 'theme-toggle';
    const ROOT_ELEMENT = document.documentElement;

     // Применяеем тему к <html>, сохраняем в localStorage.
     // @param {string} theme - 'dark' или 'light'
    function applyTheme(theme) {
        if (theme === 'dark') {
            ROOT_ELEMENT.setAttribute('data-theme', 'dark');
        } else {
            ROOT_ELEMENT.removeAttribute('data-theme');
        }

        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (e) {
            console.warn("Could not save theme to localStorage:", e);
        }
    }

     // Инициализируем тему при загрузке страницы.
     // Приоритет: localStorage > data-default-theme > prefers-color-scheme

    function initTheme() {
        let currentTheme = 'light'; // default
        try {
            const storedTheme = localStorage.getItem(STORAGE_KEY);

            if (storedTheme) {
                // 1. Приоритет: выбор юзера, сохраненный в localStorage
                currentTheme = storedTheme;
            } else {
                // 2. Приоритет: настройка по умолчанию с сервера (.env)
                const defaultTheme = ROOT_ELEMENT.dataset.defaultTheme || 'auto';

                if (defaultTheme === 'dark' || defaultTheme === 'light') {
                    currentTheme = defaultTheme;
                } else {
                    // 3. Приоритет: системная настройка (если defaultTheme = 'auto')
                    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                    if (prefersDark) {
                        currentTheme = 'dark';
                    }
                }
            }
        } catch (e) {
            console.warn("Could not read theme settings:", e);
        }

        applyTheme(currentTheme);
        return currentTheme;
    }

    const initialTheme = initTheme();

    document.addEventListener('DOMContentLoaded', () => {
        const toggleCheckbox = document.getElementById(TOGGLE_CHECKBOX_ID);

        if (toggleCheckbox) {
            toggleCheckbox.checked = (initialTheme === 'dark');

            toggleCheckbox.addEventListener('change', () => {
                const newTheme = toggleCheckbox.checked ? 'dark' : 'light';
                applyTheme(newTheme);
            });
        }
    });

})();
