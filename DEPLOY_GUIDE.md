# 🚀 Guia de Deploy - Dashboard eShows

Este guia detalha o processo completo para fazer o deploy do dashboard online.

## 📋 Pré-requisitos

- Conta no GitHub com o código do projeto
- Conta no serviço de hospedagem (Render recomendado)
- Credenciais do Supabase (URL e KEY)

## 🎯 Opções de Hospedagem

### 1. **Render** (Recomendado) ✅
- **Prós**: Deploy via GitHub, SSL grátis, interface simples
- **Plano Free**: 750 horas/mês, 512MB RAM
- **Plano Starter**: $7/mês, 2GB RAM (recomendado para produção)

### 2. **Railway**
- **Prós**: Deploy rápido, boa performance
- **Custo**: ~$5-10/mês (sem plano grátis)

### 3. **Heroku**
- **Prós**: Plataforma madura, confiável
- **Custo**: $7/mês (Eco Dyno)

## 📝 Passo a Passo - Deploy no Render

### Etapa 1: Preparação Local

#### 1.1 Verificar arquivos criados
Certifique-se que os seguintes arquivos existem:
- ✅ `render.yaml` - Configuração do Render
- ✅ `runtime.txt` - Versão do Python
- ✅ `requirements.txt` - Atualizado com gunicorn
- ✅ `app/main.py` - Com `server = app.server` adicionado

#### 1.2 Commitar mudanças
```bash
git add render.yaml runtime.txt requirements.txt app/main.py
git commit -m "feat: preparar projeto para deploy no Render"
git push origin agent5
```

### Etapa 2: Configurar no Render

#### 2.1 Criar conta e conectar GitHub
1. Acesse [render.com](https://render.com) e crie uma conta
2. Conecte sua conta do GitHub ao Render
3. Autorize o acesso ao repositório `octaviobcosta/dash-eshows`

#### 2.2 Criar novo Web Service
1. Clique em "New +" → "Web Service"
2. Selecione o repositório `dashboard-eshows`
3. Configure:
   - **Name**: `dashboard-eshows`
   - **Branch**: `agent5` (ou a branch que você usar)
   - **Root Directory**: deixe vazio
   - **Runtime**: Python (será detectado automaticamente)

#### 2.3 Configurar variáveis de ambiente
No painel do Render, adicione as seguintes variáveis:

```
SUPABASE_URL=<sua_url_supabase>
SUPABASE_KEY=<sua_chave_supabase>
JWT_SECRET_KEY=<será gerado automaticamente>
FLASK_SECRET_KEY=<será gerado automaticamente>
```

⚠️ **IMPORTANTE**: 
- Pegue `SUPABASE_URL` e `SUPABASE_KEY` do seu arquivo `.env` local
- Não inclua o `SUPABASE_DB_PASSWORD` (não é necessário para runtime)

### Etapa 3: Deploy

1. Clique em "Create Web Service"
2. O Render iniciará o build automaticamente
3. Acompanhe os logs do build
4. Após conclusão, você receberá uma URL: `https://dashboard-eshows.onrender.com`

### Etapa 4: Verificação e Testes

#### 4.1 Testar acesso
1. Acesse a URL fornecida
2. Você deve ver a tela de login
3. Use suas credenciais cadastradas no Supabase

#### 4.2 Monitorar logs
- No painel do Render, vá em "Logs" para ver logs em tempo real
- Verifique por erros de conexão com Supabase
- Monitore uso de memória

## 🔧 Troubleshooting

### Problema: Out of Memory
**Solução**: 
- Upgrade para plano Starter ($7/mês) com 2GB RAM
- Ou adicione variável: `USE_RAM_CACHE=false`

### Problema: Timeout no build
**Solução**:
- Reduza dependências desnecessárias em requirements.txt
- Use Python 3.11 (mais eficiente)

### Problema: Erro de conexão Supabase
**Solução**:
- Verifique as variáveis SUPABASE_URL e SUPABASE_KEY
- Confirme que o projeto Supabase está ativo

## 🚀 Otimizações para Produção

### 1. Performance
```yaml
# No render.yaml, ajuste o comando start:
startCommand: gunicorn app.main:server --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --max-requests 1000
```

### 2. Segurança
- Use senhas fortes para usuários
- Mantenha JWT_SECRET_KEY e FLASK_SECRET_KEY secretos
- Configure CORS se necessário

### 3. Monitoramento
- Configure alertas no Render para downtime
- Use o painel de métricas para monitorar uso

## 📱 Próximos Passos

1. **Custom Domain**: Configure domínio próprio nas configurações do Render
2. **SSL**: Já incluído automaticamente
3. **Backup**: Configure backup regular do Supabase
4. **CI/CD**: Deploys automáticos ao fazer push na branch

## 💰 Estimativa de Custos

- **Render Starter**: $7/mês
- **Supabase**: Grátis até 500MB
- **Total**: ~$7/mês para começar

## 🆘 Suporte

- Render: [docs.render.com](https://docs.render.com)
- Supabase: [supabase.com/docs](https://supabase.com/docs)
- Issues: [github.com/octaviobcosta/dash-eshows/issues](https://github.com/octaviobcosta/dash-eshows/issues)