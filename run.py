#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

# Добавляем корень проекта в пути поиска модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Запуск EnergoBot RELOAD...")
    import Bot_new
    Bot_new.main()
