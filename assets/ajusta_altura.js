document.addEventListener("DOMContentLoaded", function() {

    const cardsContainer = document.querySelector("#cards-container");
    const chartsContainer = document.querySelector("#charts-container");

    function ajustarMaxHeight() {
      if (!cardsContainer || !chartsContainer) return;

      const alturaCards = cardsContainer.offsetHeight;
      const margemExtra = 50;
      const maxHeight = alturaCards + margemExtra;

      chartsContainer.style.maxHeight = maxHeight + "px";
    }

    // Chamar ao carregar a página
    ajustarMaxHeight();

    // Se quiser recálculo ao redimensionar a janela
    window.addEventListener("resize", ajustarMaxHeight);

    // Se quiser recálculo ao clicar em algum botão (por exemplo “trocar container”):
    const btnToggle = document.getElementById("btnToggle"); 
    if (btnToggle) {
      btnToggle.addEventListener("click", function() {
        ajustarMaxHeight();
      });
    }
    console.log(">> Script ajusta_altura.js carregado com sucesso!");

});
