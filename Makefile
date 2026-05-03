.PHONY: help setup up logs down restart update stop

help:
	@echo "BuscaMaes Droplet Commands"
	@echo ""
	@echo "Setup (first time only):"
	@echo "  make setup        Clone repo, configure .env, start bot"
	@echo ""
	@echo "Operations:"
	@echo "  make up           Start bot (build + up -d)"
	@echo "  make logs         Follow live logs"
	@echo "  make logs-brief   Show last 20 lines"
	@echo "  make restart      Restart bot (no rebuild)"
	@echo "  make down         Stop bot"
	@echo "  make update       Pull latest + rebuild + start"
	@echo "  make status       Show container status"

setup:
	git clone git@github.com:maravfe/busca-maes-bot.git
	cd busca-maes-bot && cp .env.example .env && vim .env
	cd busca-maes-bot && docker compose up -d --build

up:
	docker compose up -d --build

logs:
	docker compose logs -f

logs-brief:
	docker compose logs --tail=20

restart:
	docker compose restart

down:
	docker compose down

update:
	git pull && docker compose up -d --build && docker compose logs -f

status:
	docker compose ps
