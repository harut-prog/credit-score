from locust import HttpUser, between, task

PAYLOAD = {
    "unsecured_lines": 0.3,
    "age": 35,
    "past_30_59": 0,
    "past_90": 0,
    "past_60_89": 0,
    "debt_ratio": 0.5,
    "monthly_income": 5000.0,
    "credit_lines": 5,
    "real_estate": 1,
    "dependents": 2,
}

class CreditUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(3)
    def predict(self):
        self.client.post("/v1/predict", json=PAYLOAD, name="/v1/predict")

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")