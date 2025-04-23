#!/usr/bin/env python3
import asyncio
import sys
import os

# ANSI коды для цветов (для наглядности), отключаются если NO_COLOR=1
if os.environ.get('NO_COLOR'):
    GREEN = ""
    RED = ""
    YELLOW = ""
    RESET = ""
    BOLD = ""
else:
    GREEN = "\033[92m"  # зеленый
    RED = "\033[91m"    # красный
    YELLOW = "\033[93m" # желтый
    RESET = "\033[0m"   # сброс цвета
    BOLD = "\033[1m"    # жирный

# Имитация процесса голосования
async def demonstrate_voting_widget():
    print("\n=== НАГЛЯДНАЯ ДЕМОНСТРАЦИЯ ВИДЖЕТА (ТОЛЬКО ТО, ЧТО ВИДИТ ПОЛЬЗОВАТЕЛЬ) ===\n")
    
    # 1. Начальное состояние после отправки мема
    print("🤖 Бот: Ваш мем отправлен на модерацию.")
    print("[Кнопка]: Голосование: (✅ 0 | ⚡ 0 | ❌ 0)")
    print("-" * 60)
    await asyncio.sleep(1)
    
    # 2. После первого голоса
    print("\n🤖 Бот: Ваш мем отправлен на модерацию.")
    print("[Кнопка]: Голосование: (✅ 1 | ⚡ 0 | ❌ 0)")
    print("-" * 60)
    await asyncio.sleep(1)
    
    # 3. После второго голоса
    print("\n🤖 Бот: Ваш мем отправлен на модерацию.")
    print("[Кнопка]: Голосование: (✅ 1 | ⚡ 1 | ❌ 0)")
    print("-" * 60)
    await asyncio.sleep(1)
    
    # 4. После третьего голоса
    print("\n🤖 Бот: Ваш мем отправлен на модерацию.")
    print("[Кнопка]: Голосование: (✅ 1 | ⚡ 1 | ❌ 1)")
    print("-" * 60)
    await asyncio.sleep(1)
    
    # Финальное решение
    if len(sys.argv) > 1:
        result = sys.argv[1]
    else:
        result = "approve"  # По умолчанию показываем одобрение
    
    if result == "approve":
        # Одобрение обычное
        print("\n🤖 Бот: Ваш мем отправлен на модерацию.")
        print(f"[Кнопка]: {GREEN}✅ Одобрен{RESET} (✅ 3 | ⚡ 0 | ❌ 2)")
        print("-" * 60)
        await asyncio.sleep(1)
        
        # После планирования публикации
        print("\n🤖 Бот: Ваш мем отправлен на модерацию.")
        print(f"[Кнопка]: {GREEN}✅ Одобрен{RESET} (✅ 3 | ⚡ 0 | ❌ 2) • Публикация: 15:30 UTC (через 30 мин.)")
        
    elif result == "urgent":
        # Срочная публикация
        print("\n🤖 Бот: Ваш мем отправлен на модерацию.")
        print(f"[Кнопка]: {YELLOW}⚡ Одобрен срочно{RESET} (✅ 1 | ⚡ 2 | ❌ 0)")
        
    else:
        # Отклонение
        print("\n🤖 Бот: Ваш мем отправлен на модерацию.")
        print(f"[Кнопка]: {RED}❌ Отклонён{RESET} (✅ 0 | ⚡ 1 | ❌ 3)")
    
    print("-" * 60)
    
# Функция-обертка не нужна, удаляем ее

# Для запуска из командной строки
if __name__ == "__main__":
    asyncio.run(demonstrate_voting_widget())
else:
    # Функция-обертка для запуска из других модулей, например в GitHub Actions
    def run_demonstration():
        asyncio.run(demonstrate_voting_widget())