import { OpportunityDossier } from "@/components/opportunities/opportunity-dossier";

export default async function OpportunityDetailPage({params}:{params:Promise<{id:string}>}){
  const {id}=await params;
  return <OpportunityDossier identifier={id}/>;
}
