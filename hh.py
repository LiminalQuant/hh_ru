import streamlit as st
import requests
import time
import openpyxl
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

# 🧩 Получение вакансий и Excel + возврат DataFrame
def get_vacancies_df_and_excel(search_text):
    params = {
        'text': search_text,
        'area': 1,  # Москва
        'per_page': 50,
        'page': 0
    }

    base_url = 'https://api.hh.ru/vacancies'
    salaries = []
    data_list = []

    # Excel-файл
    wb = openpyxl.Workbook()
    ws = wb.active
    safe_title = f"Вакансии {search_text}".replace(":", " ").strip()[:31]
    ws.title = safe_title
    ws.append(['Название', 'Компания', 'Город', 'Зарплата (RUR)', 'Ссылка', "lat", "lng" ])

    while True:
        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            st.error("Ошибка запроса к API HeadHunter")
            return pd.DataFrame(), None, []

        data = response.json()
        
       for vacancy in data["items"]:
            name = vacancy.get("name")
            link = vacancy.get("alternate_url")
        
            employer = vacancy.get("employer", {}).get("name")
            area = vacancy.get("area", {}).get("name")
        
            salary = vacancy.get("salary")
        
            salary_text = ""
            salary_value = None
        
            if salary and salary.get("currency") == "RUR":
                sal_from = salary.get("from")
                sal_to = salary.get("to")
        
                if sal_from and sal_to:
                    salary_value = (sal_from + sal_to) / 2
                elif sal_from:
                    salary_value = sal_from
                elif sal_to:
                    salary_value = sal_to
        
                if salary_value:
                    salary_text = int(salary_value)
                    salaries.append(salary_value)
        
            # === ДОБАВЛЯЕМ ADDRESS (БЕЗ ЛОМКИ СТРУКТУРЫ) ===
            address = vacancy.get("address") or {}
        
            raw_address = address.get("raw")
        
            lat = address.get("lat")
            lng = address.get("lng")
        
            metro = address.get("metro") or {}
            metro_lat = metro.get("lat")
            metro_lng = metro.get("lng")
        
            # fallback на метро
            if lat is None and metro_lat is not None:
                lat = metro_lat
                lng = metro_lng
        
            # ---- Excel (РАСШИРЯЕМ, НЕ МЕНЯЕМ) ----
            ws.append([
                name,
                employer,
                area,
                salary_text,
                link,
                raw_address,
                lat,
                lng
            ])
        
            # ---- DataFrame (СОХРАНЯЕМ СТАРЫЕ КЛЮЧИ) ----
            data_list.append({
                "Название": name,
                "Компания": employer,
                "Город": area,
                "Зарплата (RUR)": salary_text,
                "Ссылка": link,
                "address_raw": raw_address,
                "lat": lat,
                "lng": lng
            })


        params['page'] += 1
        if params['page'] >= data['pages']:
            break
        time.sleep(0.5)

    # Средняя в Excel
    if salaries:
        avg_salary = int(sum(salaries) / len(salaries))
        ws.append([])
        ws.append(['Средняя зарплата (по найденным):', '', '', avg_salary, ''])

    # Сохраняем Excel в память
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    df = pd.DataFrame(data_list)
    return df, output, salaries


# ========== Streamlit UI ==========
st.set_page_config(page_title="HH вакансии", layout="centered")
st.title("🔍 Поиск вакансий HH + анализ")

# 🔹 Инициализация
df = pd.DataFrame()
salaries = []
excel_file = None

# 🔹 Ввод текста
search_input = st.text_input("Введите ключевое слово (например, 'медси')", value="медси")

# 🔹 Кнопка поиска
if st.button("📥 Получить данные"):
    with st.spinner("Собираем данные..."):
        df, excel_file, salaries = get_vacancies_df_and_excel(search_input)

    if not df.empty:
        st.success(f"✅ Загружено вакансий: {len(df)}")

        # 📋 Предпросмотр
        st.subheader("📋 Предварительный просмотр")
        st.dataframe(df.head(15))

        # 📊 Гистограмма
        if salaries:
            st.subheader("📊 Распределение зарплат")
            fig, ax = plt.subplots()
            ax.hist(salaries, bins=15, color='skyblue', edgecolor='black')
            ax.set_xlabel("Зарплата (RUR)")
            ax.set_ylabel("Количество вакансий")
            ax.set_title("Гистограмма зарплат")
            st.pyplot(fig)

        # 📁 Кнопка скачивания Excel
        st.subheader("📁 Скачать полный файл")
        st.download_button(
            label="📄 Скачать Excel",
            data=excel_file,
            file_name=f"vacancies_{search_input}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# 🔍 Средняя по названию
st.subheader("📈 Средняя зарплата по названию вакансии")
vacancy_name_input = st.text_input("Введите название или часть названия")

if not df.empty and vacancy_name_input:
    filtered_df = df[df['Название'].str.contains(vacancy_name_input, case=False, na=False)]

    if not filtered_df.empty:
        filtered_salaries = (
            filtered_df['Зарплата (RUR)']
            .replace('', pd.NA)
            .dropna()
            .astype(int)
        )

        if not filtered_salaries.empty:
            avg_salary = int(filtered_salaries.mean())
            st.markdown(f"**🔹 Средняя зарплата по '{vacancy_name_input}': {avg_salary:,} руб.**".replace(",", " "))
        else:
            st.info(f"Вакансии найдены, но зарплаты не указаны.")
    else:
        st.warning("❌ Вакансии не найдены по введённому названию.")
