import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';

interface RefreshButtonProps {
  readonly queryKeys?: readonly (readonly unknown[])[]; // optional explicit keys
  readonly title?: string;
  readonly size?: 'icon' | 'sm' | 'default';
  readonly className?: string;
}

export function RefreshButton({ queryKeys, title='Refresh', size='icon', className }: RefreshButtonProps){
  const qc = useQueryClient();
  const [spinning,setSpinning] = useState(false);
  const doRefresh = async ()=>{
    setSpinning(true);
    try{
      if(queryKeys?.length){
        await Promise.all(queryKeys.map(k=> qc.invalidateQueries({ queryKey: k })));
      } else {
        // Fallback: invalidate common resource keys
        await Promise.all([
          qc.invalidateQueries({queryKey:['patients']}),
          qc.invalidateQueries({queryKey:['drugs']}),
          qc.invalidateQueries({queryKey:['deliveries']}),
          qc.invalidateQueries({queryKey:['inventory']}),
        ]);
      }
    } finally {
      setTimeout(()=> setSpinning(false), 400); // small delay for UX
    }
  };
  return (
    <Button variant="outline" size={size} aria-label={title} onClick={doRefresh} disabled={spinning} className={className}>
      <RefreshCw className={['h-4 w-4 transition-transform', spinning? 'animate-spin':'' ].join(' ')} />
    </Button>
  );
}
