import AtlasLoader from '@/components/atlas-loader';

// Render the initial shell immediately. The API can cold-start independently,
// without blocking the HTML response of the Next.js page.
export default function Page() {
  return <AtlasLoader />;
}
