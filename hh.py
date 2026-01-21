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
    salaries_max = []
    data_list = []

    # Excel-файл
    wb = openpyxl.Workbook()
    ws = wb.active
    safe_title = f"Вакансии {search_text}".replace(":", " ").strip()[:31]
    ws.title = safe_title

    ws.append([
        'Название', 'Компания', 'Город',
        'salary_min', 'salary_max', 'salary_mean',
        'Ссылка', 'Адрес', 'lat', 'lng'
    ])

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

            salary_min = None
            salary_max = None
            salary_mean = None

            if salary and salary.get("currency") == "RUR":
                salary_min = salary.get("from")
                salary_max = salary.get("to")

                if salary_min is not None and salary_max is not None:
                    salary_mean = (salary_min + salary_max) / 2
                else:
                    salary_mean = salary_min or salary_max

                if salary_max is not None:
                    salaries_max.append(salary_max)

            # === ADDRESS ===
            address = vacancy.get("address") or {}
            raw_address = address.get("raw")

            lat = address.get("lat")
            lng = address.get("lng")

            metro = address.get("metro") or {}
            if lat is None and metro.get("lat") is not None:
                lat = metro.get("lat")
                lng = metro.get("lng")

            # ---- Excel ----
            ws.append([
                name,
                employer,
                area,
                salary_min,
                salary_max,
                int(salary_mean) if salary_mean is not None else None,
                link,
                raw_address,
                lat,
                lng
            ])

            # ---- DataFrame ----
            data_list.append({
                "Название": name,
                "Компания": employer,
                "Город": area,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_mean": salary_mean,
                "Ссылка": link,
                "address_raw": raw_address,
                "lat": lat,
                "lng": lng
            })

        params['page'] += 1
        if params['page'] >= data['pages']:
            break
        time.sleep(0.5)

    # Средняя MAX по всем вакансиям (для справки)
    if salaries_max:
        ws.append([])
        ws.append([
            'Средняя MAX зарплата:',
            '', '', '', int(sum(salaries_max) / len(salaries_max)), ''
        ])

    # Excel → память
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    df = pd.DataFrame(data_list)
    return df, output, salaries_max


# ========== Streamlit UI ==========
st.set_page_config(page_title="HH вакансии", layout="centered")
st.title("🔍 HH вакансии — анализ зарплат")

df = pd.DataFrame()
salaries_max = []
excel_file = None

search_input = st.text_input("Введите ключевое слово", value="медси")

if st.button("📥 Получить данные"):
    with st.spinner("Собираем данные..."):
        df, excel_file, salaries_max = get_vacancies_df_and_excel(search_input)

    if not df.empty:
        st.success(f"✅ Загружено вакансий: {len(df)}")

        st.subheader("📋 Предпросмотр")
        st.dataframe(df.head(15))

        if salaries_max:
            st.subheader("📊 Распределение MAX зарплат")
            fig, ax = plt.subplots()
            ax.hist(salaries_max, bins=15, edgecolor='black')
            ax.set_xlabel("MAX зарплата (RUR)")
            ax.set_ylabel("Количество вакансий")
            ax.set_title("Гистограмма MAX зарплат")
            st.pyplot(fig)

        st.subheader("📁 Скачать Excel")
        st.download_button(
            label="📄 Скачать Excel",
            data=excel_file,
            file_name=f"vacancies_{search_input}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )