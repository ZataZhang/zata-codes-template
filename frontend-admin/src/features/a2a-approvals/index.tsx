import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  approveA2APeer,
  listPendingA2APeers,
  type A2APeerApproval,
} from '@/api/agents'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'

/** 渲染平台待审核的 A2A 目标队列。 */
export function A2AApprovals() {
  const { t } = useTranslation()
  const [peers, setPeers] = useState<A2APeerApproval[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    listPendingA2APeers()
      .then((pendingPeers) => {
        if (!cancelled) setPeers(pendingPeers)
      })
      .catch(() => {
        if (!cancelled) setError(String(t('a2aApprovals.loadFailed')))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [t])

  /** 管理员确认组织与端点后批准外部 A2A 目标。 */
  const approve = async (peer: A2APeerApproval) => {
    try {
      await approveA2APeer(peer.id)
      setPeers((currentPeers) => currentPeers.filter((item) => item.id !== peer.id))
      toast.success(t('a2aApprovals.approved'))
    } catch {
      toast.error(t('a2aApprovals.approveFailed'))
    }
  }

  return (
    <>
      <Header fixed>
        <div className='ml-auto flex items-center gap-4'>
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className='mb-6'>
          <h1 className='text-2xl font-bold tracking-tight'>
            {t('a2aApprovals.title')}
          </h1>
          <p className='text-muted-foreground'>
            {t('a2aApprovals.description')}
          </p>
        </div>
        {error && (
          <p role='alert' className='mb-4 text-sm text-destructive'>
            {error}
          </p>
        )}
        <div className='grid gap-4'>
          {peers.map((peer) => (
            <Card key={peer.id}>
              <CardHeader>
                <CardTitle className='flex flex-wrap items-center justify-between gap-3'>
                  <span>{peer.name}</span>
                  <Button size='sm' onClick={() => void approve(peer)}>
                    {t('a2aApprovals.approve')}
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent className='grid gap-2 text-sm'>
                <p className='break-all'>
                  <strong>{t('a2aApprovals.organization')}:</strong>{' '}
                  <code>{peer.organization_id}</code>
                </p>
                <p className='break-all'>
                  <strong>{t('agents.cardUrl')}:</strong> {peer.card_url}
                </p>
                <p className='break-all'>
                  <strong>{t('agents.endpointUrl')}:</strong> {peer.endpoint_url}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
        {!loading && peers.length === 0 && (
          <p className='text-sm text-muted-foreground'>
            {t('a2aApprovals.empty')}
          </p>
        )}
      </Main>
    </>
  )
}
