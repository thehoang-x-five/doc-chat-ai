import { ReactNode } from 'react';
import { twMerge } from 'tailwind-merge';

interface CardProps {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

const Card = ({ title, description, actions, children, className }: CardProps) => {
  return (
    <div className={twMerge('card-elevated p-4 sm:p-6 bg-card/80 backdrop-blur', className)}>
      {(title || actions) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h3 className="text-base font-semibold">{title}</h3>}
            {description && <p className="text-sm text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="shrink-0">{actions}</div>}
        </div>
      )}
      {children}
    </div>
  );
};

export default Card;
