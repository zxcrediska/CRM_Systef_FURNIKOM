import requests
import json

url = "http://127.0.0.1:8000/crm/api/lead/create/"

# Данные заявки
data = {
    "name": "Иван Петров",
    "phone": "+7 (999) 888-77-66",
    "company_name": "ООО Мебельщик",
    "email": "ivan@mebel.ru",
    "message": "Требуется поставка петель для корпусной мебели на сумму 500 000 руб.",
    "subject": "Запрос на поставку фурнитуры",
    "source": "telegram"
}

headers = {
    "Content-Type": "application/json"
}

response = requests.post(url, data=json.dumps(data), headers=headers)

print(f"Статус: {response.status_code}")
print(f"Ответ: {response.json()}")