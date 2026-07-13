import { Button, StatePanel } from "@bighead/ui";
import { transverseStates } from "./transverse-states";

export function TransverseStateCatalog() {
  return <div className="bh-state-grid" data-testid="transverse-state-catalog">
    <StatePanel aria-label="Loading" data-responsive="desktop mobile" kind="loading" title="Loading"><p>{transverseStates[0].description}</p><span className="bh-skeleton" data-testid="loading-skeleton">Carregando conteudo</span></StatePanel>
    <StatePanel action={<Button type="button">Criar primeiro item</Button>} data-responsive="desktop mobile" kind="empty" title="Vazio"><p>{transverseStates[1].description}</p></StatePanel>
    <StatePanel action={<Button type="button">Tentar novamente</Button>} data-responsive="desktop mobile" kind="error" title="Erro"><p>{transverseStates[2].description}</p></StatePanel>
    <StatePanel data-responsive="desktop mobile" data-testid="permission-state" kind="permission" title="Sem permissao"><p>{transverseStates[3].description}</p></StatePanel>
    <StatePanel action={<Button type="button">Reconectar</Button>} data-responsive="desktop mobile" kind="offline" title="Offline"><p>{transverseStates[4].description}</p></StatePanel>
    <StatePanel action={<a href="#catalog-next-action">Continuar</a>} data-responsive="desktop mobile" kind="success" title="Sucesso"><p>{transverseStates[5].description}</p></StatePanel>
  </div>;
}
