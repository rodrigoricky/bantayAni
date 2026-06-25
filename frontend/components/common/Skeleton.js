export default function Skeleton({ className = '', width, height, rounded = false }) {
  return (
    <div
      className={`bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 animate-shimmer bg-[length:200%_100%] ${
        rounded ? 'rounded-full' : 'rounded'
      } ${className}`}
      style={{ width, height }}
    />
  );
}