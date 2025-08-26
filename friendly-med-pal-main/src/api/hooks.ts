import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, retry } from './client';

// Types (simplified)
export interface Patient { id: number; name: string; age?: number; condition?: string; contact?: string; }
export interface Drug { id: number; name: string; dosage?: string; stock?: number; reorder_level?: number; }
export interface Delivery { id: number; patient_id: number; drug_id: number; scheduled_for: string; status: string; notes?: string; quantity?: number; }
export interface InventorySummary { id:number; pending_quantity?:number; daily_avg?:number; days_supply?:number; }
export interface InventoryMerged extends Drug, InventorySummary {}
export interface InventoryTransaction { id:number; drug_id:number; delta:number; reason?:string; created_at:string; }

// Keys
const keys = {
  patients: ['patients'] as const,
  drugs: ['drugs'] as const,
  deliveries: ['deliveries'] as const,
  stats: ['stats'] as const,
  inventory: ['inventory'] as const,
  inventorySummary: ['inventory','summary'] as const,
  inventoryTransactions: ['inventory','transactions'] as const,
};

export function usePatients(){
  return useQuery({ queryKey: keys.patients, queryFn: ()=> retry(()=> api<Patient[]>('/patients')) });
}
export function useDrugs(){
  return useQuery({ queryKey: keys.drugs, queryFn: ()=> retry(()=> api<Drug[]>('/drugs')) });
}
export function useDeliveries(){
  return useQuery({ queryKey: keys.deliveries, queryFn: ()=> retry(()=> api<Delivery[]>('/deliveries')) });
}
export function useStats(){
  return useQuery({ queryKey: keys.stats, queryFn: ()=> api<any>('/stats') });
}
export function useInventoryDrugs(){
  return useQuery({ queryKey: keys.inventory, queryFn: ()=> retry(()=> api<Drug[]>('/drugs')) });
}
export function useInventorySummary(){
  return useQuery({ queryKey: keys.inventorySummary, queryFn: ()=> api<InventorySummary[]>('/inventory/summary') });
}
export function useInventoryTransactions(limit=200){
  return useQuery({ queryKey: [...keys.inventoryTransactions, limit], queryFn: ()=> api<InventoryTransaction[]>(`/inventory/transactions?limit=${limit}`)});
}
export function usePatientDeliveries(patientId?: number){
  return useQuery({
    queryKey: ['patient-deliveries', patientId],
    queryFn: ()=> patientId? api<Delivery[]>(`/deliveries/patient/${patientId}`): Promise.resolve([]),
    enabled: !!patientId,
  });
}

// Mutations
export function useAddPatient(){
  const qc=useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Patient>)=> api<Patient>('/patients',{method:'POST', body: JSON.stringify(data)}),
    onSuccess: ()=> qc.invalidateQueries({queryKey: keys.patients}),
  });
}
export function useAddDrug(){
  const qc=useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Drug>)=> api<Drug>('/drugs',{method:'POST', body: JSON.stringify(data)}),
    onSuccess: ()=> qc.invalidateQueries({queryKey: keys.drugs}),
  });
}
export function useAddDelivery(){
  const qc=useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Delivery>)=> api<Delivery>('/deliveries',{method:'POST', body: JSON.stringify(data)}),
    onSuccess: ()=> qc.invalidateQueries({queryKey: keys.deliveries}),
  });
}
export function useUpdateDeliveryStatus(){
  const qc=useQueryClient();
  return useMutation({
    mutationFn: ({id,status}:{id:number;status:string})=> api<Delivery>(`/deliveries/${id}/status`,{method:'PATCH', body: JSON.stringify({status})}),
    onSuccess: ()=> qc.invalidateQueries({queryKey: keys.deliveries}),
  });
}
export function useAdjustInventory(){
  const qc=useQueryClient();
  return useMutation({
    mutationFn: ({drug_id,delta,reason}:{drug_id:number;delta:number;reason?:string})=> api<any>('/inventory/adjust',{method:'POST', body: JSON.stringify({drug_id, delta, reason})}),
    onSuccess: ()=>{
      qc.invalidateQueries({queryKey: keys.inventory});
      qc.invalidateQueries({queryKey: keys.inventorySummary});
      qc.invalidateQueries({queryKey: keys.inventoryTransactions});
    }
  });
}

// Derived selector utilities
export function mergeInventory(drugs?:Drug[], summary?:InventorySummary[]): InventoryMerged[]{
  if(!drugs) return [];
  const map=new Map(summary?.map(s=>[s.id,s])||[]);
  return drugs.map(d=> ({...d, ...(map.get(d.id)||{})}));
}
