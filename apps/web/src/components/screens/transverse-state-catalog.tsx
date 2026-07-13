import { transverseStates } from "./transverse-states";

export function TransverseStateCatalog() {
  return (
    <div className="bh-state-grid" data-testid="transverse-state-catalog">
      <div aria-busy="true" aria-label="Loading" className="bh-state-panel">
        <strong>Loading</strong>
        <p>{transverseStates[0].description}</p>
        <span className="bh-skeleton" data-testid="loading-skeleton">Carregando conteúdo</span>
      </div>
      <div className="bh-state-panel">
        <strong>Vazio</strong>
        <p>{transverseStates[1].description}</p>
        <button type="button">Criar primeiro item</button>
      </div>
      <div className="bh-state-panel bh-state-panel-risk" role="alert">
        <strong>Erro</strong>
        <p>{transverseStates[2].description}</p>
        <button type="button">Tentar novamente</button>
      </div>
      <div className="bh-state-panel" data-testid="permission-state">
        <strong>Sem permissao</strong>
        <p>{transverseStates[3].description}</p>
      </div>
      <div className="bh-state-panel" role="status">
        <strong>Offline</strong>
        <p>{transverseStates[4].description}</p>
        <button type="button">Reconectar</button>
      </div>
      <div className="bh-state-panel" role="status">
        <strong>Sucesso</strong>
        <p>{transverseStates[5].description}</p>
        <a href="#catalog-next-action">Continuar</a>
      </div>
    </div>
  );
}
