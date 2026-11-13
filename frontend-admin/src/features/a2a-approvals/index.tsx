import { useCallback, useEffect, useState } from 'react'
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

/** Render the platform's pending A2A destination review queue. */
export function A2AApprovals() {
  const { t } = useTranslation()
  const [peers, setPeers] = useState<A2APeerApproval[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  /** Reload the queue from the authenticated platform API. */
  const refresh = useCallback(async () => {
    try {
      setPeers(await listPendingA2APeers())
      setError('')
    } catch {
      setError(String(t('a2aApprovals.loadFailed')))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void refresh()
  }, [refresh])

  /** Approve a peer after an operator verifies its organization and endpoint. */
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
