#!/bin/bash
# Script para configurar aliases úteis do Git
# Execute com: bash scripts/git-aliases.sh

echo "Configurando aliases úteis do Git..."

# Aliases para visualização
git config alias.lg "log --oneline --graph --decorate --all"
git config alias.ll "log --pretty=format:'%C(yellow)%h%Cred%d %Creset%s%Cblue [%cn]' --decorate --numstat"
git config alias.ls "log --pretty=format:'%C(yellow)%h%Cred%d %Creset%s%Cblue [%cn]' --decorate"

# Aliases para status
git config alias.s "status -s"
git config alias.st "status"

# Aliases para branches
git config alias.br "branch"
git config alias.co "checkout"
git config alias.cob "checkout -b"

# Aliases para commits
git config alias.ci "commit"
git config alias.cm "commit -m"
git config alias.amend "commit --amend"

# Aliases para trabalho remoto
git config alias.p "push"
git config alias.pl "pull"
git config alias.f "fetch"

# Aliases úteis
git config alias.unstage "reset HEAD --"
git config alias.last "log -1 HEAD"
git config alias.visual "!gitk"
git config alias.contributors "shortlog -sn"

echo "✅ Aliases configurados com sucesso!"
echo ""
echo "Aliases disponíveis:"
echo "  git lg     - Log gráfico bonito"
echo "  git ll     - Log detalhado com estatísticas"
echo "  git s      - Status resumido"
echo "  git co     - Checkout"
echo "  git cob    - Checkout nova branch"
echo "  git cm     - Commit com mensagem"
echo "  git p      - Push"
echo "  git pl     - Pull"
echo "  git last   - Ver último commit"