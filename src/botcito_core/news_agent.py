from transformers import pipeline
import logging

# Configuración básica de logging
logger = logging.getLogger(__name__)

class FinancialNewsAgent:
    def __init__(self):
        """
        Inicializa el agente usando FinBERT.
        Este modelo es específico para finanzas (ProsusAI/finbert).
        """
        logger.info("Cargando modelo de Análisis de Sentimiento Financiero (FinBERT)...")
        # El pipeline descarga el modelo automáticamente la primera vez
        self.analyzer = pipeline("text-classification", model="ProsusAI/finbert")

    def analyze_sentiment(self, headlines: list[str]) -> float:
        """
        Analiza una lista de titulares y devuelve un puntaje de sentimiento agregado.
        
        Args:
            headlines: Lista de titulares de noticias (strings).
            
        Returns:
            float: Un valor entre -1.0 (Muy Negativo) y 1.0 (Muy Positivo).
                   El 0.0 representa neutralidad o falta de noticias.
        """
        if not headlines:
            return 0.0

        # FinBERT procesa los textos
        results = self.analyzer(headlines)
        total_score = 0.0

        for result in results:
            # result es algo como: {'label': 'positive', 'score': 0.95}
            label = result['label']
            score = result['score'] # Confianza del modelo (0 a 1)

            if label == 'positive':
                total_score += score
            elif label == 'negative':
                total_score -= score
            # Si es 'neutral', sumamos 0

        # Promedio simple del sentimiento de todas las noticias
        return total_score / len(headlines)