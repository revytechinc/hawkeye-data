PORTNAME=	hawkeye-data
PORTVERSION=	0.1.0
CATEGORIES=	sysutils

MAINTAINER=	mark@cloudbsd.org
COMMENT=	Offline knowledge kit for Hawkeye (FTS playbooks)
WWW=		https://github.com/revytechinc/hawkeye-data

LICENSE=	BSD3CLAUSE
LICENSE_FILE=	${WRKSRC}/LICENSE

USE_GITHUB=	yes
GH_ACCOUNT=	revytechinc
GH_PROJECT=	hawkeye-data

# Sibling of sysutils/hawkeye (binaries). This port is data only.
NO_ARCH=	yes
NO_BUILD=	yes

# pkg copy. Rescue copy is /boot/hawkeye (see pkg-message); not installed by default.
DATADIR=	${PREFIX}/share/hawkeye

do-install:
	${MKDIR} ${STAGEDIR}${DATADIR}/playbooks \
		${STAGEDIR}${DATADIR}/schema \
		${STAGEDIR}${DATADIR}/docs
	${INSTALL_DATA} ${WRKSRC}/share/knowledge.sqlite ${STAGEDIR}${DATADIR}
	${INSTALL_DATA} ${WRKSRC}/schema/knowledge.sql ${STAGEDIR}${DATADIR}/schema
	${INSTALL_DATA} ${WRKSRC}/README.md ${STAGEDIR}${DATADIR}
	cd ${WRKSRC}/playbooks && ${COPYTREE_SHARE} . ${STAGEDIR}${DATADIR}/playbooks
	cd ${WRKSRC}/docs && ${COPYTREE_SHARE} . ${STAGEDIR}${DATADIR}/docs

.include <bsd.port.mk>
