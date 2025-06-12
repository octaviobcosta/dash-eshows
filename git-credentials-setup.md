# Configuração de Credenciais Git

## Opção 1: Git Credential Manager (Recomendado para Windows)

No PowerShell como administrador:
```powershell
# Instalar Git Credential Manager
winget install --id Git.Git -e --source winget

# Configurar para usar o Git Credential Manager
git config --global credential.helper manager-core
```

## Opção 2: Usando Personal Access Token com Store

1. Criar arquivo de credenciais:
```bash
# Linux/WSL
echo "https://octaviobcosta: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@github.com" > ~/.git-credentials

# Windows PowerShell
echo "https://octaviobcosta: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@github.com" > $HOME\.git-credentials
```

2. Configurar Git para usar o store:
```bash
git config --global credential.helper store
```

## Opção 3: Usando SSH (Mais Seguro)

1. Gerar chave SSH:
```bash
ssh-keygen -t ed25519 -C "octavio@eshows.com.br"
```

2. Adicionar chave ao ssh-agent:
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

3. Copiar chave pública:
```bash
cat ~/.ssh/id_ed25519.pub
```

4. Adicionar no GitHub: Settings > SSH and GPG keys > New SSH key

5. Mudar remote para SSH:
```bash
git remote set-url origin git@github.com:octaviobcosta/dash-eshows.git
```

## Opção 4: Cache Temporário (Atual)

Configuração atual que mantém credenciais por 1 hora:
```bash
git config --global credential.helper 'cache --timeout=3600'
```

## Verificar Configuração

```bash
# Ver configuração atual
git config --global credential.helper

# Testar conexão
git ls-remote origin
```

## Segurança

⚠️ **IMPORTANTE**: 
- Nunca commite tokens ou senhas no repositório
- Use tokens com escopo mínimo necessário
- Revogue tokens não utilizados
- Prefira SSH para maior segurança

## Remover Credenciais Salvas

```bash
# Linux/WSL
rm ~/.git-credentials

# Windows
del %USERPROFILE%\.git-credentials

# Limpar cache
git config --global --unset credential.helper
```