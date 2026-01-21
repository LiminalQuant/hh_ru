import streamlit as st
import requests
import time
import openpyxl
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

# ==============================
# HH FETCH + NORMALIZATION
# ==============================
def get_vacancies_df_and_excel(search_text):
    params = {
        "text": search_text,
        "area": 1,  # Москва
        "per_page": 50,
        "page": 0,
    }

    base_url = "https://api.hh.ru/vacancies"

    rows = []
    salaries_max = []

    # Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Вакансии {search_text}"[:31]

    ws.append([
        "Название",
        "Компания",
        "Город",
        "salary_min",
        "salary_max",
        "salary_mean",
        "Ссылка",
        "address_raw",
        "lat",
        "lng",
    ])

    while True:
        resp = requests.get(base_url, params=params)
        if resp.status_code != 200:
            st.error("Ошибка API HH")
            return pd.DataFrame(), None, []

        data = resp.json()

        for v in data["items"]:
            name = v.get("name")
            link = v.get("alternate_url")
            employer = v.get("employer", {}).get("name")
            area = v.get("area", {}).get("name")

            # ---------- SALARY ----------
            salary = v.get("salary")

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

                # ориентир = MAX
                if salary_max is not None:
                    salaries_max.append(salary_max)
                elif salary_min is not None:
                    salaries_max.append(salary_min)

            # ---------- ADDRESS ----------
            address = v.get("address") or {}
            raw_address = address.get("raw")

            lat = address.get("lat")
            lng = address.get("lng")

            metro = address.get("metro") or {}
            if lat is None and metro.get("lat") is not None:
                lat = metro.get("lat")
                lng = metro.get("lng")

            row = {
                "Название": name,
                "Компания": employer,
                "Город": area,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_mean": salary_mean,
                "Ссылка": link,
                "address_raw": raw_address,
                "lat": lat,
                "lng": lng,
            }

            rows.append(row)

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
                lng,
            ])

        params["page"] += 1
        if params["page"] >= data["pages"]:
            break

        time.sleep(0.4)

    # Excel → memory
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    df = pd.DataFrame(rows)
    return df, output, salaries_max


# ==============================
# STREAMLIT UI
# ==============================
st.set_page_config(page_title="HH зарплаты", layout="centered")
st.title("🔍 HH — анализ зарплат (MAX / MEAN)")

search_text = st.text_input("Ключевое слово", value="медси")

df = pd.DataFrame()
excel_file = None
salaries_max = []

if st.button("📥 Получить данные"):
    with st.spinner("Загружаем HH..."):
        df, excel_file, salaries_max = get_vacancies_df_and_excel(search_text)

    if not df.empty:
        st.success(f"Загружено вакансий: {len(df)}")

        # ---------- PREVIEW ----------
        st.subheader("📋 Предпросмотр")
        st.dataframe(df.head(20))

        # ---------- HIST MAX ----------
        if salaries_max:
            st.subheader("📊 Распределение MAX зарплат")
            fig, ax = plt.subplots()
            ax.hist(salaries_max, bins=15, edgecolor="black")
            ax.set_xlabel("MAX зарплата (RUR)")
            ax.set_ylabel("Количество вакансий")
            ax.set_title("Потолки зарплат")
            st.pyplot(fig)

        # ---------- DOWNLOAD ----------
        st.subheader("📁 Скачать Excel")
        st.download_button(
            "📄 Скачать файл",
            data=excel_file,
            file_name=f"vacancies_{search_text}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ==============================
# ANALYTICS UI — MEAN
# ==============================
if not df.empty:
    st.divider()

    st.subheader("📈 Средняя зарплата по рынку (MEAN)")

    vacancy_filter = st.text_input(
        "Фильтр по названию вакансии",
        placeholder="администратор-кассир",
    )

    if vacancy_filter:
        filtered = df[
            df["Название"].str.contains(vacancy_filter, case=False, na=False)
        ]

        valid_means = filtered["salary_mean"].dropna().astype(float)

        if not valid_means.empty:
            st.success(
                f"Средняя по рынку: **{int(valid_means.mean()):,} ₽**"
                .replace(",", " ")
            )
        else:
            st.info("Зарплаты не указаны.")

    st.subheader("🏢 Средняя зарплата по компании")

    company_filter = st.text_input(
        "Фильтр по компании",
        placeholder="МЕДСИ",
    )

    if company_filter:
        filtered = df[
            df["Компания"].str.contains(company_filter, case=False, na=False)
        ]

        valid_means = filtered["salary_mean"].dropna().astype(float)

        if not valid_means.empty:
            st.success(
                f"Средняя по компании: **{int(valid_means.mean()):,} ₽**"
                .replace(",", " ")
            )
        else:
            st.info("Зарплаты не указаны.")
